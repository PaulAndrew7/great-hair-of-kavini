# Evaluation

All numbers here are from `data/evaluation/report.json`, generated on 2026-09-28 by `backend/scripts/evaluate.py` against catalog `997a4813-dd69c366`, rules `2026-09-28.1`, model `all-MiniLM-L6-v2 @ 1110a243fdf4`, RRF k = 60, depth 50 per channel, semantic floor 0.30. The Evaluation screen displays the same report. Re-running the script regenerates every number from the frozen inputs.

## Method

**Inputs, frozen before any output was inspected** (`data/evaluation/`):

| File | Contents |
|---|---|
| `queries.json` | 18 learning goals, 6 per track: 2 development + 4 held-out test each (6 dev, 12 test). 5 edge cases. The relevance rule. |
| `profiles.json` | 9 student profiles, 3 per track, each with a hand-written expected set of missing skills. Two include chip edits. |
| `judgments.json` | 187 relevance labels, each with a one-line reason. |

**Retrieval.** Each goal goes through the same goal parser Discover uses (so "I know Python and SQL" is removed from the search text), then through each of the three modes of the shared engine: BM25 only, semantic only, and hybrid (RRF). Personalisation is not applied, so the comparison is of retrieval alone.

**Judging.** For every goal, the top 5 of all three modes were pooled and shown sorted by course ID, with method and rank hidden (`evaluate.py pool`). A course is relevant when its main subject is the topic the goal asks for and it respects explicit constraints such as "beginner". The judge was Claude, an AI assistant, working from title, organization, level, catalog skills and description. **The labels await review by the project author**; the plan asked for human judgments, and changing any label in `judgments.json` and re-running recomputes the report. Scoring refuses to run if any top-5 result is unjudged.

**Metrics.**
- Precision@5 = relevant results in the top 5 / 5. Unfilled positions count as misses.
- MRR@5 = 1 / rank of the first relevant result, or 0 if none is in the top 5.
- Skill gaps: precision, recall and F1 of predicted missing skills against the expected set, micro-averaged over the 9 profiles, plus exact-set matches. Tracks are auto-detected, as in the app.
- Paths (same 9 profiles): mean goal-skill coverage after the path, unresolved skills, duplicate courses, and prerequisite violations. A step violates if a course's modelled prerequisite, or a skill dependency of what it teaches, is not covered by the student's skills plus earlier steps.
- Latency: 30 warm `/recommend` requests in-process through FastAPI (routing, validation, serialisation; no network hop), cycling through the 18 goals after 3 warm-ups. Cold start covers catalog load, BM25 build and model load, after Python imports.

Tuning discipline: the semantic floor (0.30) and other retrieval settings were set during development, before the query set existed. Nothing was changed after the test results were seen.

## Results

### Search relevance

| Split | Method | Precision@5 | MRR@5 |
|---|---|---:|---:|
| Dev (6) | Keyword (BM25) | 0.73 | 0.81 |
| | Semantic (MiniLM) | **0.93** | **1.00** |
| | Hybrid (RRF) | 0.90 | **1.00** |
| Test (12) | Keyword (BM25) | 0.63 | 0.75 |
| | Semantic (MiniLM) | **0.87** | 0.83 |
| | Hybrid (RRF) | 0.75 | **0.90** |

Per query (Precision@5, BM25 / semantic / hybrid):

| Query | BM25 | Sem. | Hyb. | | Query | BM25 | Sem. | Hyb. |
|---|---:|---:|---:|---|---|---:|---:|---:|
| ml-d1 move into ML | 0.4 | 1.0 | 1.0 | | da-t1 spreadsheets of sales | 0.4 | 1.0 | 0.8 |
| ml-d2 recognise images | 1.0 | 0.8 | 0.6 | | da-t2 become a data analyst | 0.8 | 1.0 | 1.0 |
| da-d1 beginner to advanced | 0.6 | 1.0 | 1.0 | | da-t3 clean and visualise | 0.8 | 0.8 | 0.8 |
| da-d2 Tableau dashboards | 1.0 | 1.0 | 1.0 | | da-t4 Power BI reporting | 1.0 | 1.0 | 1.0 |
| cc-d1 cloud from basics | 0.8 | 1.0 | 1.0 | | cc-t1 Docker and Kubernetes | 0.8 | 1.0 | 1.0 |
| cc-d2 AWS Cloud Practitioner | 0.6 | 0.8 | 0.8 | | cc-t2 cloud engineering | 0.0 | 0.8 | 0.2 |
| ml-t1 predictive models | 1.0 | 1.0 | 0.8 | | cc-t3 renting servers | 0.2 | 0.6 | 0.2 |
| ml-t2 TensorFlow | 0.8 | 1.0 | 1.0 | | cc-t4 Google Cloud beginners | 0.4 | 0.4 | 0.6 |
| ml-t3 regression, classification | 1.0 | 1.0 | 1.0 | | | | | |
| ml-t4 beginner intro to ML | 0.4 | 0.8 | 0.6 | | | | | |

### Skill gaps (9 profiles)

| Precision | Recall | F1 | Exact-set matches |
|---:|---:|---:|---:|
| 0.96 | 1.00 | 0.98 | 7 of 9 |

Tracks were detected correctly for all nine. The two misses are both false positives, a skill the student has but the parser did not read:

- ml-p3, "I don't know any programming yet but I **studied calculus at school**": Calculus counted as missing. The parser's known-skill cues include "I have studied" but not "I studied".
- cc-p2, "I know Linux and **networking**": Networking counted as missing. "networking" on its own is not one of the parser's surface forms for the Networking skill.

Negation held in da-p3 ("Statistics and Excel but not SQL" kept SQL in the gap), and the chip edits in ml-p3 (Statistics) and cc-p3 (Linux) were applied.

### Learning paths (same 9 profiles)

| Mean goal-skill coverage after path | Unresolved skills | Duplicate courses | Prerequisite violations | Steps with unverified prerequisites |
|---:|---:|---:|---:|---:|
| 1.00 | 0 | 0 | 0 | 0 |

**Manual order review** (by Claude, reading each path in `report.json`; also awaiting author review):

- Order is sound in all nine: foundations (Linux and Networking; Calculus, Linear Algebra and Statistics; Spreadsheets and Statistics) come first, and goal skills follow their dependencies.
- Some credited skills are generous. In ml-p2, *Mathematics for Machine Learning and Data Science Specialization* is credited with Machine Learning and Regression because its catalog tags list them and its embedding is close to both. In cc-p3, *Network Principles in Practice: Linux Networking* is credited with Kubernetes from a catalog tag. A reviewer would likely not count either as the student's main source for those skills. Zero violations means the modelled rules were respected, not that every credited skill is well taught.
- da-p2 starts with *Data Science for Health Research Specialization* for Statistics and Data Cleaning: correct skills, but a domain-specific programme for a general analyst.

### What-If behaviour

Checked through the API for every missing skill of the three example goals (21 simulations), and in the browser:

- Most simulations change one to three courses. Two leave the path unchanged (Cloud Platforms for the beginner cloud goal, SQL for the analytics goal), and the UI says "No path change" with no step flagged as new.
- Two make the path longer: Cloud Computing (cloud goal, 4 to 5 courses) and Spreadsheets (analytics goal, 4 to 5). This is a greedy-selection effect (see [design.md](design.md), section 6), reported as it happens rather than hidden.
- Four rapid toggles (Containers, Linux, Networking, Linux off) ended with the UI showing exactly the path the API returns for the final state, Containers + Networking; confirmed skills were unchanged. A unit test checks that a simulation equals a normal request with the same effective skills.

### Speed (Windows 11, AMD64 Family 25, 16 logical CPUs, Python 3.13, CPU inference)

| Warm requests | Median | 95th percentile | Cold start |
|---:|---:|---:|---:|
| 30 | 28 ms | 32 ms | 12.8 s |

Well under the two-second target for a warm recommendation. Across four runs the median ranged from 26 to 29 ms and the 95th percentile from 32 to 34 ms.

### Edge cases

| Case | Expected | Observed | Result |
|---|---|---|---|
| Empty goal | Rejected with a message | HTTP 422 "Describe what you want to learn." | Pass |
| Unrelated subject (violin) | No chart or path; unsupported-track warning | No chart or path; warning; 5 search results | Pass |
| Filters with no matches | Zero courses, "loosen a filter", empty path | 0 eligible, 0 shown, 0 steps; filters warning | Pass |
| Negated known skill | SQL known, Python not | Confirmed SQL; Python negated and in the gap | Pass |
| Ambiguous track ("work with data in the cloud") | Ask which track | Detected cloud computing; path shown | **Fail** |

The ambiguity check fires only when two tracks' detection phrases both match. "data" alone is not a data-analytics phrase, so the goal went straight to cloud computing. The student can still switch track with the Track control, but the system did not ask.

## What the results mean

**Semantic retrieval does most of the work.** It leads Precision@5 on both splits. It is strongest where the goal and the catalog use different words: "renting servers and storage over the internet" (0.6 against 0.2 for BM25) and "help me move into cloud engineering" (0.8 against 0.0).

**Equal-weight fusion costs precision on noisy keyword queries.** For "help me move into cloud engineering", BM25's top five are all *data engineering* courses (they match both "cloud" and "engineering"). RRF gives those courses as much weight as the semantic channel's cloud-computing results, and hybrid drops to 0.2. The same happens with literal "hardware" and "storage" matches for cc-t3. A second effect shows on ml-d2 (image recognition), where hybrid scores below *both* channels: courses ranked moderately in both lists (general neural-network and generative courses) outrank courses ranked highly in only one.

**Hybrid still has a role.** It has the best test MRR@5 (0.90): it puts a relevant course first more often than either channel alone, and keywords matter for exact tool names (all three modes are perfect on Tableau and Power BI). The served mode stays hybrid, as planned, because switching after seeing test results would be tuning on the test set. The next step is to compare channel weights, or a semantic floor applied to keyword hits, on a new held-out query set.

**Profile reading is good but rule-bound.** Recall of missing skills is perfect; the two errors are unrecognised phrasings, each fixable with one rule. They should be fixed together with new profiles that were not used to find them.

## Limitations

- One judge, and an AI one. The labels are reproducible and have reasons, but they have not yet been checked by a person.
- Pooled judgments cover only the compared runs; no catalog-wide recall is claimed.
- 18 queries is a small sample: one test query moves a split's Precision@5 by up to 0.08.
- Skill-gap expectations follow the project's curated track definitions. They test profile reading and gap arithmetic, not whether the curriculum is right.
- Only 8 courses have reviewed prerequisites; path "violations" can only be checked against modelled rules.
- Latency was measured on one development machine.

## Reproduce

```powershell
cd backend
.venv\Scripts\python scripts\evaluate.py pool   # after changing queries, ranking or data: lists unjudged candidates, blind
# add labels for anything listed to data/evaluation/judgments.json
.venv\Scripts\python scripts\evaluate.py        # writes data/evaluation/report.json
```
