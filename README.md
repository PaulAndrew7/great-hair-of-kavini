# Prior — University Course Finder

Prior turns a learning goal written in plain language ("I know Python and SQL. Help me move into machine learning.") into:

1. up to five relevant courses from a 6,642-course Coursera catalog, each with an **Honest Advisor** explanation (why it helps, what to know first and where that prerequisite came from, what to watch out for);
2. a skill chart showing what the student already has and what is missing, in learning order;
3. a short, ordered **learning path** built from real catalog courses;
4. a **What-If** toggle that recomputes gaps and path as if the student already knew a skill, and shows the real change, including "no change".

It runs locally: one FastAPI service (hybrid BM25 + sentence-embedding retrieval, skill-gap and path logic, SQLite feedback) and one React app with two screens, Discover and Evaluation. No LLM, no paid API, no vector database. After a one-time download it works offline.

| Deliverable | Where |
|---|---|
| **Plain-language guide to the whole project and website** | [docs/how-it-works.md](docs/how-it-works.md) |
| Architecture diagram (PDF and JPEG) | [docs/architecture.pdf](docs/architecture.pdf), [docs/architecture.jpg](docs/architecture.jpg) |
| Design decisions and trade-offs | [docs/design.md](docs/design.md) |
| Data preparation and quality report | [docs/data-quality.md](docs/data-quality.md) |
| Evaluation method and measured results | [docs/evaluation.md](docs/evaluation.md) |
| Demo script (10-minute panel) | [docs/demo-script.md](docs/demo-script.md) |
| Implementation plan and progress tracker | [implementation-plan.md](implementation-plan.md) |
| Executable microservice | [backend/](backend/) |
| User application | [frontend/](frontend/) |

## Setup

Tested on Windows 11 with Python 3.13 and Node 22. Commands are shown for PowerShell; on macOS or Linux use `.venv/bin/python` instead of `.venv\Scripts\python`.

### 1. Backend

```powershell
cd backend
python -m venv .venv
# CPU-only PyTorch keeps the install small; install it before the other requirements.
.venv\Scripts\python -m pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -r requirements.txt
```

### 2. Dataset and model (one-time download, about 110 MB)

```powershell
.venv\Scripts\python scripts\fetch_inputs.py
```

This downloads the pinned snapshot `coursera_course_2024.csv` from the Hugging Face dataset [azrai99/coursera-course-dataset](https://huggingface.co/datasets/azrai99/coursera-course-dataset) (revision `ccd36c16`) into `data/raw/`, checks its SHA-256, and caches `sentence-transformers/all-MiniLM-L6-v2` (revision `1110a243`) in `models/`. Files already present and verified are skipped. On Windows, a warning about symlinks and Developer Mode is harmless.

The processed catalog and embeddings in `data/processed/` are already built from that snapshot. To rebuild them:

```powershell
.venv\Scripts\python scripts\prepare_data.py   # clean CSV -> courses.json + data_quality.json (deterministic)
.venv\Scripts\python scripts\build_index.py    # embeddings.npy, course_ids.json, manifest.json
```

The service checks at startup that the catalog, IDs, embeddings and manifest belong together, and refuses to serve mismatched artifacts.

### 3. Run

Two terminals:

```powershell
# terminal 1, from backend/
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
```

```powershell
# terminal 2, from frontend/
npm ci
npm run dev
```

Open http://localhost:5173. The top bar shows "6,642 courses · Hybrid search ready" when the service is up. The service takes about 12 seconds to start (catalog, BM25 index and model load); the API docs are at http://127.0.0.1:8100/docs.

Port 8100 is used because 8000 is often taken. To use another port, start uvicorn with `--port N` and point the frontend at it before `npm run dev`: `$env:PRIOR_API = "http://127.0.0.1:N"` (PowerShell) or `PRIOR_API=http://127.0.0.1:N npm run dev` (bash). For a production build: `npm run build`, then `npm run preview` (serves `dist/` on port 4173 with the same API proxy).

## Sample usage

In the app, press the first example goal, or type your own and press Enter. Remove any skill chip that isn't true, pick filters, press "Why this course" on a result, and press a blue or yellow tile in the chart to try a What-If.

The same pipeline over HTTP:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8100/recommend -ContentType application/json `
  -Body '{"goal": "I know Python and SQL. Help me move into machine learning."}'
```

```bash
curl -s -X POST http://127.0.0.1:8100/recommend -H 'Content-Type: application/json' \
  -d '{"goal": "I know Python and SQL. Help me move into machine learning."}'
```

Abbreviated real response (catalog `997a4813-dd69c366`):

```text
profile:      track machine_learning (detected); confirmed skills Python, SQL (read from the goal)
skill gap:    goal skills missing  Machine Learning, Regression, Deep Learning
              foundations missing  Calculus, Linear Algebra, Statistics
              coverage             0 of 3 goal skills now, 3 of 3 after the path
courses:      1 Machine Learning Introduction for Everyone (IBM, Beginner, 4.5)
                why:    matches your goal by keyword and by meaning; teaches Machine Learning and Deep Learning
                before: curated guidance puts Calculus, Linear Algebra, Python and Statistics first; you have Python
              2 Machine Learning Foundations: A Case Study Approach (University of Washington, 4.6)
              3 Foundations of Machine Learning (Fractal Analytics, Beginner) - also step 3 of the path
              ...
path:         1 Mathematics for Machine Learning Specialization   -> Calculus, Linear Algebra
              2 Statistics and Data Analysis with Excel, Part 1   -> Statistics
              3 Foundations of Machine Learning                   -> Machine Learning, Regression
              4 Structuring Machine Learning Projects             -> Deep Learning
timing:       about 25 ms once warm
```

What-If is the same call with `"simulated_skills": ["Statistics"]`; simulated skills never enter the confirmed profile. Filters: `"filters": {"difficulty": "Beginner", "organization": "IBM", "min_rating": 4.5}`. Unknown ratings or levels never satisfy a filter.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Readiness, retrieval mode (hybrid or keyword-only), data version |
| `GET /catalog` | Tracks, track skills, organizations, filter choices |
| `POST /recommend` | Full result: profile, courses with explanations, skill gap, path, warnings. Also used for What-If |
| `POST /search` | Raw `bm25`, `semantic` or `hybrid` retrieval, for evaluation and debugging |
| `POST /feedback` | Stores Relevant / Not relevant / Too advanced / Too basic / Already learned in SQLite |
| `GET /evaluation` | The latest saved evaluation report (never runs models) |

Skill charts and learning paths cover three tracks: machine learning, data analytics and cloud computing. Any other goal still gets search results, with a clear "no structured path" message.

## Tests and evaluation

```powershell
cd backend
.venv\Scripts\python -m pytest -q                 # 31 checks: cleaning, skills/paths, API, degraded mode
.venv\Scripts\python scripts\evaluate.py          # writes data/evaluation/report.json, shown on the Evaluation screen
.venv\Scripts\python scripts\evaluate.py pool     # lists unjudged top-5 results after queries or ranking change
```

Queries, profiles and relevance judgments live in `data/evaluation/`. Scoring refuses to run while any top-5 result is unjudged. Results and their limits are discussed in [docs/evaluation.md](docs/evaluation.md).

```powershell
cd frontend
npm run build    # type-check and production build
npm run lint
```

## Project layout

```text
backend/app/        main.py (routes, startup), schemas.py (API contract), catalog.py, cleaning.py, search.py (BM25,
                    embeddings, RRF), skills.py (goal parsing, tracks), prerequisites.py, learning_path.py,
                    recommend.py (the /recommend pipeline), advisor.py (Honest Advisor), feedback.py, config.py
backend/scripts/    fetch_inputs.py, prepare_data.py, build_index.py, evaluate.py
backend/tests/      pytest suites
frontend/src/       App.tsx, api.ts, types.ts (mirrors schemas.py), pages/ (Discover, Evaluation), components/
data/raw/           the unmodified source CSV
data/processed/     courses.json, embeddings.npy, course_ids.json, manifest.json, data_quality.json
data/rules/         skill_aliases.json, goal_skills.json, course_prerequisites.json, course_overrides.json
data/evaluation/    queries.json, profiles.json, judgments.json, report.json
docs/               architecture, design, data quality, evaluation, demo script
```

`models/` (downloaded) and `backend/feedback.sqlite3` (runtime) are not part of the source; `fetch_inputs.py` and the first feedback submission recreate them.

## Troubleshooting

| Symptom | Fix |
|---|---|
| The app says "The course service is not running" | Start uvicorn on port 8100 (step 3), then press Retry. |
| Top bar says "Keyword search only" | The embedding model is not in `models/`. Run `scripts\fetch_inputs.py` and restart the backend. Results are labelled keyword-only until then. |
| `/health` is `unavailable` and names a catalog error | `data/processed/` is missing or mismatched. Run `prepare_data.py` then `build_index.py`. |
| `error while attempting to bind on address` | Something already uses port 8100. Stop it, or pick another port as described in step 3. |
| Evaluation screen says "Not evaluated yet" | Run `scripts\evaluate.py`, then reload the page. |
| Calling the API from another origin fails with CORS | Set `PRIOR_CORS_ORIGINS` to a comma-separated list of origins before starting uvicorn. The dev server proxies `/api`, so the app itself does not need this. |
