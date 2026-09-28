# Data preparation and quality

All numbers below were observed on the frozen snapshot by `backend/scripts/prepare_data.py` and `build_index.py`, and are stored in `data/processed/data_quality.json` and `manifest.json`. Nothing here comes from the earlier 42-page proposal, whose 623-row file was never supplied.

## Source

| Item | Value |
|---|---|
| Dataset | Hugging Face `azrai99/coursera-course-dataset` (alternative link in the brief) |
| File | `coursera_course_2024.csv`, revision `ccd36c1660fee9610d5262e7517d8397c343168b` |
| Downloaded | 2026-09-28 |
| SHA-256 | `997a4813b0b9f0d808512f5370a85ae710ed7ecd06dc11c3029253310c3ed4a7` |
| Columns | index, title, enrolled, rating, num_reviews, Instructor, Organization, Skills, Description, Modules/Courses, Level, Schedule, URL, Satisfaction Rate |
| Rows in | 6,645 |
| Courses out | 6,642 |
| Data version | `997a4813-dd69c366` (source hash prefix + processed catalog hash prefix) |

One file is used, as the brief requires. Nothing is merged by row position.

## What cleaning does

| Step | Rule | Observed |
|---|---|---|
| Duplicates | Drop exact duplicate records and duplicate canonical URLs | 3 exact duplicates dropped; 0 duplicate URLs; 0 missing titles |
| Stable IDs | `course_id` is a short hash of the canonical URL (fallback: organization + title), with deterministic collision handling | Re-running on the same snapshot produces byte-identical `courses.json` (verified by SHA-256 in M1) |
| Missing values | Missing stays missing: no rating is `null`, never 0; no level is `Unknown`, never Beginner | Missing: rating 1,434; level 778; skills 1,953; duration 1,887; description 10 |
| Skills | String-encoded lists parsed with a safe literal parser (never `eval`); 9,134 raw labels normalised through `data/rules/skill_aliases.json` to 8,670 canonical skills | Related concepts stay separate: "Computer Programming" is not Python, "Bayesian Statistics" is not Statistics |
| Scraper artefacts | Activity counts glued into descriptions ("8 videos9 readings4 quizzes") are removed | Covered by a unit test |
| Shared descriptions | A description identical across different courses is marked `Suspect` and is not used for search or display | 82 groups, 195 courses flagged (for example Bachelor's and Master's versions of the same course) |
| Title/description mismatch | Each description's embedding is compared with its own title and skills; below 0.12 cosine it is marked `Suspect` | 6,437 checked; median 0.664, 1st percentile 0.354; 1 flagged ("JavaScript Security Part 2", 0.033) |
| Course type | Derived from the URL: Course, Specialization, Professional Certificate | 5,619 / 909 / 114 |

Final description quality: 6,436 Unreviewed, 196 Suspect, 10 Missing, 0 Reviewed. A Suspect or Missing description is excluded from both search channels; the course remains searchable by its title and skills, and the UI says why no summary is shown. `data/rules/course_overrides.json` holds manual per-course decisions with reasons; it is currently empty.

Level distribution: Beginner 3,589, Intermediate 2,023, Advanced 252, Unknown 778.

## Track skills

Skill gaps and paths use 21 track skills defined in `data/rules/goal_skills.json`. A course counts as teaching one when its catalog tags map to it or its title matches the skill's title pattern. 1,577 courses teach at least one track skill (1,985 tag matches, 523 title matches).

| Skill | Courses | Skill | Courses | Skill | Courses |
|---|---:|---|---:|---|---:|
| Python | 234 | Spreadsheets | 83 | Linux | 78 |
| SQL | 99 | Data Analysis | 340 | Networking | 83 |
| Statistics | 141 | Data Cleaning | 35 | Cloud Computing | 146 |
| Linear Algebra | 26 | Data Visualization | 184 | Cloud Platforms | 300 |
| Calculus | 32 | BI Dashboards | 109 | Containers | 35 |
| Machine Learning | 252 | | | Kubernetes | 43 |
| Regression | 85 | | | DevOps | 70 |
| Deep Learning | 95 | | | Cloud Security | 38 |

Every track skill has at least 26 courses, so each supported track can be covered by real catalog courses. Tags list tools a course uses as well as what it teaches (a regression course tagged Calculus), so at service start each tag is also marked *primary* or *listed* by comparing the course embedding with the skill; only primary skills count toward a learning path.

## Knowledge base artefacts

| File | Contents |
|---|---|
| `courses.json` | 6,642 canonical course records, sorted by `course_id` |
| `embeddings.npy` | 6,642 x 384 float32, L2-normalised, same order as `course_ids.json` |
| `course_ids.json` | Row order of the embeddings |
| `manifest.json` | Source hash, preprocessing version, rule-file hashes, model name and revision, embedding recipe, artefact hashes and shape |

Embedding text recipe: `title. Skills: skill list.` followed by the first 160 words of the description when it is not Suspect or Missing. Title and skills come first because MiniLM truncates input at 256 word pieces. The service refuses to start if the IDs, embeddings, catalog and manifest disagree.
