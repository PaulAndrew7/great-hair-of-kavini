# Design decisions and trade-offs

Prior answers one question for a student: *what should I learn next, and why?* The design keeps every answer traceable to catalog data or a labelled rule, so a student (and a panel) can see why a course was chosen and where the system is unsure.

See [architecture.pdf](architecture.pdf) for the data-to-recommendation flow.

## 1. Shape of the system

**One service, one app, files on disk.** The backend is a single FastAPI process with ordinary Python modules (catalog, search, skills, prerequisites, learning path, advisor, feedback). The frontend is a React + Vite app with two screens. Artefacts are JSON and NumPy files; feedback goes to SQLite.

- *Why:* the catalog is 6,642 courses. A 6,642 x 384 matrix is 10 MB; exact cosine similarity over it takes a few milliseconds. A vector database, message queue or second service would add setup steps and failure modes without a measured need.
- *Trade-off:* the service holds everything in memory and starts in about 12 seconds (catalog load, BM25 index build, model load). That is acceptable for a local demo; a larger catalog would need a persisted BM25 index and an approximate-nearest-neighbour index.

**No LLM.** Explanations are templates filled from the recommendation's own data.

- *Why:* every sentence the student reads can be traced to a catalog field or a rule, nothing is invented, it runs offline and costs nothing per request.
- *Trade-off:* explanations are less fluent than generated text, and the goal parser understands fewer phrasings than a language model would (the evaluation shows two misses, section 9).

## 2. Data preparation

Choices are detailed with numbers in [data-quality.md](data-quality.md). The principles:

- **Freeze one snapshot and record its hash.** Every artefact, rule review and evaluation label refers to catalog version `997a4813-dd69c366`.
- **Missing stays missing.** An unknown rating does not become 0, an unknown level does not become Beginner, and an unknown value never satisfies an explicit filter.
- **Distrust descriptions that don't belong to their course.** 196 descriptions are marked Suspect (shared across different courses, or unrelated to the title) and are kept out of both search channels.
- **Stable IDs from URLs.** Course IDs survive re-runs, so judgments, prerequisite reviews and feedback stay attached to the right course.
- **Refuse misaligned artefacts.** The manifest records hashes of the catalog, IDs and embeddings; the service will not serve a mismatch.

## 3. Retrieval

1. **Filters first.** Difficulty, organization and minimum rating define the eligible set before either channel runs, so a filter cannot silently drop a relevant course that sat below a cut-off.
2. **Keyword channel:** BM25 over title, skills and validated description, with light stemming and stop words. A hit that shares no query term is discarded.
3. **Semantic channel:** `all-MiniLM-L6-v2` (pinned revision) cosine similarity over the same eligible set, with a floor of 0.30 so unrelated goals return nothing rather than the least-bad course.
4. **Fusion:** Reciprocal Rank Fusion, `sum(1 / (60 + rank))` over the top 50 of each channel, ties broken by course ID so results are deterministic.

Retrieval runs on the goal's *target text*: the goal parser removes clauses about what the student already knows ("I know Python and SQL"), so known skills do not pull in courses the student doesn't need.

**Why hybrid:** keywords catch exact tool names (Tableau, Power BI, TensorFlow); embeddings catch paraphrases ("renting servers over the internet" for cloud computing). RRF needs no score calibration between the two channels.

**What the evaluation showed:** on the 12 held-out queries, semantic-only retrieval had the highest Precision@5 (0.87 against 0.75 for hybrid), while hybrid had the highest MRR@5 (0.90). Equal-weight RRF lets a noisy keyword channel dilute good semantic results: for "help me move into cloud engineering", BM25's top five are all *data* engineering courses. Hybrid remains the served mode because it was the planned design, it puts a relevant course first most often, and changing it now would be tuning on the test set. Weighting the channels, or requiring keyword hits to clear a semantic floor, is the first thing to try with a fresh held-out query set. See [evaluation.md](evaluation.md).

**Scores are not shown as percentages.** Fusion scores and cosine similarities are not probabilities of suitability; the UI shows ranks and reasons instead of "95% match".

## 4. Skills, tracks and prerequisites

**Three modelled tracks** (machine learning, data analytics, cloud computing), 21 skills, and 13 curated dependency rules in `data/rules/goal_skills.json`, each with a written reason. The graph is checked for cycles at startup. Other goals get search results and a plain "no structured path" message, not invented advice.

- *Why:* a small, reviewed curriculum is something we can defend line by line. Generating a skill graph for every subject would produce advice we could not check.
- *Trade-off:* coverage is narrow, and the curriculum reflects common university sequencing, not an official standard.

**Every prerequisite relation names its source.**

| Source | Meaning | Count |
|---|---|---|
| Course description | A reviewed entry in `course_prerequisites.json` quoting the catalog text | 8 courses |
| Curated guidance | Derived from the dependencies of the skills the course teaches | Any course teaching a track skill |
| Not verified | Neither of the above | Shown as "Prerequisites not verified", never as "none" |

**Tags are evidence, not proof.** A catalog skill tag counts toward a path only when the course is mainly about it (title match, or course embedding close to the skill). A course that lists Calculus in passing is not scheduled as the Calculus step.

## 5. Reading the student

The goal parser splits the goal into clauses and looks for polarity cues: "I know / I use / I'm comfortable with" marks skills as known; "don't know / new to / not" marks them as not known; "want / help me / learn" marks the target. Detected skills appear as editable chips.

- **The student's corrections win.** Removing a chip sends it as an exclusion; adding one sends it as known. Inference never overrides an edit.
- **Negation is respected.** "I don't know Python yet" never marks Python as known.
- **Ambiguity is surfaced.** When a goal matches two tracks, the student is asked to choose; nothing is guessed.
- *Trade-off:* a rule-based parser misses phrasings it has no rule for. The evaluation found two: "I studied calculus at school" and "networking" as a bare word.

## 6. Personalisation and the learning path

**Recommendations** re-rank only the top 10 relevant fused results: courses whose modelled prerequisites the student meets come first, then unknown, then unmet; within each group, courses that teach more missing goal skills come first; then fused rank; rating only breaks ties. Relevance gates everything, so an irrelevant course cannot climb because the student happens to meet its prerequisites.

**The learning path** is a deterministic greedy loop:

1. Find missing skills whose dependencies are covered (by the student or earlier steps).
2. Search the whole filtered catalog, not only the five displayed courses, for courses that mainly teach those skills.
3. Skip courses whose modelled prerequisites are unmet; prefer met over not verified.
4. Choose the course covering the most learnable missing skills; break ties by relevance to the skill and goal, suitable level for the step, then rating.
5. Repeat until everything is covered, five steps, or no progress.

What remains is reported as unresolved with a reason ("No course teaches Calculus with the current filters"). The path never relaxes the student's filters and never invents a course.

- *Why greedy:* it is explainable step by step ("step 2 because it builds on step 1"), deterministic, and fast. An optimiser would find shorter paths in some cases but could not explain its choices as simply.
- *Trade-off:* greedy choices can be locally good and globally longer. This shows up in What-If: for "I want to learn cloud computing from the basics", simulating Cloud Computing makes the path 5 courses instead of 4, because the course that covered Cloud Computing and Containers together is no longer the best first pick. The UI reports that honestly ("Path: 4 courses to 5 courses"). The skills a path adds are labelled *projected coverage after the path*, not mastery.

## 7. The two signature features

**Honest Advisor.** Each course carries three short lists built from the response data: *Why this helps* (matched terms, missing skills it teaches and the evidence source), *Before you start* (prerequisites with their source, what the student has and lacks), *Things to consider* (Advanced level with foundations missing, overlap with known skills, missing level or rating, a rating from few reviews or below most of the catalog, a suspect or missing description, a multi-course programme). A relevant concern is more useful than an unexplained score.

**What-If.** Simulated skills are sent separately from confirmed skills and run through exactly the same `/recommend` pipeline. The app keeps the baseline and simulation in separate slots, aborts stale requests when tiles are toggled quickly, and shows the actual difference: skills to get, courses added, moved or dropped, and "No path change" when that is the truth. A test checks that a simulation equals a normal request with the same effective skills. Reset restores the saved profile exactly.

## 8. Application and feedback

- **Two screens.** Discover holds the goal, skill chips, filters, the skill chart, the path and the course list; Evaluation shows the saved report. Fewer destinations keep the demo and the code small.
- **A skill chart instead of a card grid.** Skills are laid out like a periodic table: rows are learning order, black tiles are known, blue are missing goal skills, yellow are missing foundations, hatched are What-If. Pressing a tile starts a What-If. State is always conveyed by text and pattern as well as colour.
- **Honest states.** Loading, service offline (with the command to start it), keyword-only mode, no matches, filters excluded everything, unsupported track, and ambiguous track each have their own message.
- **Feedback** (Relevant, Not relevant, Too advanced, Too basic, Already learned, optional note) is stored in SQLite with the request context, using parameterised statements. It is for analysis; it does not silently retrain ranking.
- **Accessibility:** every control is keyboard-operable and labelled; tiles are buttons with full spoken descriptions; layouts stack on narrow screens (checked at 390 px wide).

## 9. Reliability

- **Offline after setup.** The model loads with `local_files_only`; the test suite passes with Hugging Face offline mode forced on.
- **Degraded mode.** If the model cannot load but the catalog is valid, the service runs keyword-only, says so in `/health`, the top bar and every response, and refuses semantic or hybrid `/search` requests rather than faking them. Covered by tests.
- **Validation.** Empty goals, invalid enums, ratings outside 0-5, oversized inputs and unknown course IDs are rejected with messages the UI can show.

## 10. Deliberately not built

| Not built | Reason |
|---|---|
| LLM chat or generated explanations | Unverifiable text; offline and cost constraints; templates suffice |
| Vector database, Elasticsearch | 6,642 vectors fit in memory; exact search is milliseconds |
| Accounts, saved profiles | Not required by the brief; avoids storing personal data |
| Automatic retraining from feedback | Too little feedback to learn from safely; would make results change without explanation |
| Automatic prerequisite extraction from descriptions | Unreliable without review; reviewed entries are labelled instead |
| More than three tracks | Each track needs a reviewed curriculum; breadth would cost honesty |

## 11. Known limitations and next steps

1. Equal-weight RRF under-performs semantic-only on Precision@5 for queries with generic keywords. Next: try channel weights or a semantic floor on keyword hits, measured on a new held-out set.
2. The goal parser missed "I studied calculus at school" and a bare "networking". Next: add these cue and surface forms, with new profiles to measure them.
3. A goal like "work with data in the cloud" is routed to cloud computing without asking. Next: treat broad "data" wording as a weak data-analytics signal that triggers the track question.
4. Only 8 courses have reviewed prerequisites; the rest rely on curated guidance.
5. Relevance judgments were made by one judge (an AI assistant, blind to method) and await author review.
