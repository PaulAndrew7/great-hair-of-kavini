# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Fixed by `implementation-plan.md` section 4: React + Vite + TypeScript frontend styled with plain CSS (shared tokens, no component-system dependency); one FastAPI + Pydantic service; pandas, rank-bm25, Sentence Transformers (`all-MiniLM-L6-v2`), NumPy; SQLite for feedback. Runs locally; no cloud deployment.

## Users

Primary: a university student deciding what to learn next, arriving with a goal in plain language ("I know Python and SQL, help me move into machine learning") and an uncertain sense of what they already know.

Primary viewing scene (confirmed): a projected 10-minute assessment panel demo (8 minutes demo, 2 minutes questions). The interface must read from across a room on a shared screen. A student using it at a laptop is the secondary scene.

## Product Purpose

Turn "What should I learn next?" into a handful of relevant catalog courses, a clear split between skills the student has and skills they still need, and a short ordered learning path the student can understand and change. Success is a student (and a panel) seeing why each course was chosen, what foundation comes first, and what would change if they already knew something else.

## Positioning

Hybrid retrieval (BM25 + local sentence embeddings, fused by Reciprocal Rank Fusion) is the engine, but the claim a keyword course search cannot copy is honesty about fit: every recommendation carries an Honest Advisor explanation (why this helps, what to know first and where that prerequisite came from, what to watch out for), and a What-If toggle recomputes gaps and path as if the student already knew a skill, showing the actual change including "no change".

## Operating Context

- Two screens only: Discover (goal, editable skill chips, filters, recommendations, gaps, path, What-If) and Evaluation (measured comparison of BM25, semantic and hybrid retrieval, skill/path checks, latency).
- Structured skill-gap analysis and learning paths are supported for three tracks: machine learning, data analytics, cloud computing. Other goals still get search results plus a clear "no structured path" message.
- Feedback labels per course: Relevant, Not relevant, Too advanced, Too basic, Already learned. Stored in SQLite for analysis; it does not retrain ranking.
- Demo story: "I know Python and SQL; I want to learn machine learning", with a beginner cloud-computing query as the second example and adding Statistics as the What-If.

## Capabilities and Constraints

- Catalog: Hugging Face `azrai99/coursera-course-dataset`, file `coursera_course_2024.csv`, commit `ccd36c1660fee9610d5262e7517d8397c343168b` (confirmed choice). Observed at intake: 6,645 rows, 14 columns (title, enrolled, rating, num_reviews, Instructor, Organization, Skills, Description, Modules/Courses, Level, Schedule, URL, Satisfaction Rate, index).
- Similarity scores are not match percentages; never display "95% match".
- Prerequisites are either explicit metadata or visibly labelled curated guidance; unreviewed prerequisites stay "not verified", never "none".
- Coverage is curriculum coverage (target skills covered / total), never a competence score. Path skills are "projected after the path", not mastered.
- No LLM, no accounts, no vector database, no paid APIs. Must work offline after setup.
- Filters: difficulty, organization, minimum rating. Unknown values never satisfy an explicit filter.

## Brand Commitments

- Product carries an invented product name of its own (confirmed); "University Course Finder" remains the descriptor. Name to be chosen during visual-world work.

## Evidence on Hand

- `problem statement.txt`: the assignment brief and grading weights.
- `Intelligent Course Discovery System.pdf`: earlier 42-page proposal, reviewed and reduced in the plan.
- `implementation-plan.md`: authoritative plan, contracts, milestones and progress tracker.
- No evaluation results, user testimonials, or usage numbers exist yet. The Evaluation screen must show "Not evaluated yet" until a real report exists; nothing may be fabricated.

## Product Principles

1. Explain before you rank: a relevant concern beats an unexplained score.
2. Show uncertainty as uncertainty: unknown prerequisites, missing ratings and suspect descriptions are labelled, not hidden or defaulted.
3. The student's corrections win over inference: detected skills are editable, simulated skills never leak into the confirmed profile.
4. Fewer, truer results: returning three honest courses beats padding to five.
5. Everything on screen comes from the same backend pipeline the evaluation measures.

## Accessibility & Inclusion

Keyboard-operable controls with labels; state conveyed by text or icon alongside colour; stacked layout on narrow screens; legible at projector distance.
