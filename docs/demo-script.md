# Demo script

The brief allows **10 minutes: 8 minutes of demo, 2 minutes of questions**. One story carries the demo: *"I know Python and SQL; I want to learn machine learning."* A beginner cloud-computing goal is the second example. Every course named below is what the system returned on catalog `997a4813-dd69c366` on 2026-09-28; nothing is hard-coded for the demo. If the catalog, rules or ranking change, re-run the demo and update this script.

## Before the panel

- [ ] Backend running on 8100 and the top bar says "6,642 courses · Hybrid search ready".
- [ ] Browser at http://localhost:5173 in **light** theme (reads best on a projector), zoom so the chart and course list are both visible.
- [ ] Discover empty (reload the page). Evaluation shows the latest report.
- [ ] Backup screenshots open in another window: `docs/screenshots/`.
- [ ] If Wi-Fi is unreliable: everything works offline except the external course links.

## 10-minute panel version

| Time | Show | Say |
|---|---|---|
| **0:00-1:00** Problem | Discover, empty. | "Students know roughly where they want to go but not what to take first. A keyword search returns hundreds of courses. Prior turns a goal into five relevant courses, a clear split between what you have and what you lack, and a short ordered path, and it tells you why." |
| **1:00-2:00** Architecture and data | Architecture diagram (`docs/architecture.pdf`). | "One FastAPI service and one React app. 6,645 Coursera rows, cleaned to 6,642: 3 duplicates dropped, missing values kept missing, 196 descriptions distrusted because they are shared or don't match the title. Search is hybrid: BM25 keywords plus local MiniLM embeddings, fused by Reciprocal Rank Fusion. No LLM and no paid API; it runs offline." |
| **2:00-4:00** Search, personalisation, Honest Advisor | Press the first example goal. Point at the chips **Python** and **SQL**. Open **Why this course** on course 1, *Machine Learning Introduction for Everyone* (IBM). | "It read Python and SQL from my sentence as editable chips. My corrections win: if I remove one, it's treated as unknown. The course list is ranked by relevance first, then by whether I have what each course builds on. The Honest Advisor says why this course fits (it teaches Machine Learning and Deep Learning, from its catalog tags), and what I'm missing first: Calculus, Linear Algebra and Statistics, from curated guidance. No '95% match'." |
| **4:00-6:00** Skill gaps, prerequisite sources, path | The *Machine learning* chart, then scroll to the learning path. | "Rows are learning order. Black is what I have, blue are goal skills I lack, yellow are foundations. Coverage: 0 of 3 goal skills now, 3 of 3 after the path, and that's catalog coverage, not mastery. The path is four real courses: step 1 *Mathematics for Machine Learning Specialization* for Calculus and Linear Algebra; step 2 *Statistics and Data Analysis with Excel, Part 1*, whose description says 'designed for students with no prior statistics knowledge'; step 3 *Foundations of Machine Learning*; step 4 *Structuring Machine Learning Projects*, which quotes 'for learners who have basic machine learning knowledge', so it comes after step 3. Every prerequisite says where it came from: the course description, curated guidance, or 'not verified'." |
| **6:00-7:00** What-If and reset | Press the yellow **St** (Statistics) tile. Then **Reset simulation**. | "What if I already knew Statistics? Skills to get drop from 6 to 5, and the path is still four courses, but three are swapped. Why: Regression only depends on Statistics, so now a calculus course that also teaches Regression can be step 1. My saved profile is unchanged: the chips still say Python and SQL. Reset brings back the original path exactly." |
| **7:00-8:00** Evaluation, feedback, one limitation | Open a course's **Why this course**, press **Too advanced** ("Saved"). Switch to **Evaluation**. | "Feedback is stored in SQLite for review; it doesn't silently retrain anything. We measured on 18 goals: 6 for development, 12 held out. On the held-out set, hybrid puts a relevant course first most often (MRR 0.90), but semantic-only has the better Precision@5, 0.87 against 0.75. Keyword matches on words like 'engineering' pull in data-engineering courses for a cloud-engineering goal. We report that rather than tune on the test set. Skill gaps were exact on 7 of 9 profiles, with no duplicate courses or prerequisite violations in any path, and a warm request takes about 30 ms." |
| **8:00-10:00** Questions | Stay on Evaluation, or return to Discover to answer with a live example. | See prepared answers below. |

**If time allows, or as a live answer:** type *"I want to learn cloud computing from the basics."* The Cloud computing chart shows 0 of 6 goal skills. The path starts with *Connecting to Devices and Networks* ("designed for learners with no technical experience"), then *Containers in the Cloud Specialization*, *Getting Started with Google Kubernetes Engine* and *Managing Security in Google Cloud*. Setting Difficulty to Beginner changes the path, and each step still states its prerequisite source.

## 20-minute walkthrough version

| Time | What to show | Main point |
|---|---|---|
| 0-2 min | The problem and the Python + SQL student | Students need a next step, not a long course list. |
| 2-4 min | Architecture diagram and [data-quality.md](data-quality.md) numbers | One local service turns a cleaned catalog into recommendations. |
| 4-8 min | Goal, chips (remove SQL to show a correction), filters (minimum rating 4.7), Honest Advisor on two courses | Why each course fits, and where caution is needed. |
| 8-12 min | Skill chart, hover a tile to show what it builds on and why, the path with quoted prerequisites | One foundation before the next course, with sources. |
| 12-15 min | What-If Statistics, the swapped steps, "Dropped in this what-if", reset | The student can explore how preparation changes the plan. |
| 15-17 min | Evaluation screen and one limitation; the feedback control | Evidence, including where the design falls short. |
| 17-20 min | Questions | Trade-offs, using the working example. |

## Prepared answers

**Why hybrid search, if semantic scored higher?**
Keywords catch exact tool names (Tableau, Power BI, TensorFlow) and embeddings catch paraphrases. On our held-out set, hybrid ranks a relevant course first most often (MRR 0.90 against 0.83), but equal-weight fusion lets noisy keyword matches dilute precision. The next step is weighting the channels, measured on a fresh held-out set. Changing it after seeing test results would be tuning on the test set.

**Where do prerequisites come from?**
Three labelled sources: a quote from the course description (8 reviewed courses), curated guidance from our skill dependencies (each with a written reason), or "not verified". We never show "none" when we don't know.

**Why no LLM or vector database?**
6,642 courses fit in a 10 MB matrix; exact search takes milliseconds. Template explanations can be traced to catalog fields, run offline and cost nothing. An LLM would add fluency but also text we couldn't verify.

**Does feedback train the system?**
No. It is stored with the request context for analysis. Automatic learning from a handful of labels would change results without explanation.

**Who judged relevance?**
One judge, an AI assistant, working blind: candidates were pooled from all three methods and shown sorted by course ID, so the method was hidden. The labels and reasons are in `data/evaluation/judgments.json` and are awaiting the author's review. Changing a label and re-running recomputes every number.

**What are the limitations?**
Three modelled tracks; imperfect catalog skill tags; a rule-based goal parser that missed "studied calculus at school" and a bare "networking"; few verified prerequisites; 18 queries is a small sample. All of these are listed on the Evaluation screen.

**Does knowing more always shorten the path?**
No, and the app doesn't pretend it does. For the beginner cloud goal, simulating Cloud Platforms gives "No path change" (the Kubernetes course is still needed for DevOps and Kubernetes), and simulating Cloud Computing makes the path one course longer, because the greedy planner loses a course that covered two skills at once. Show it live if asked.

**What happens with a goal outside the three tracks?**
With Track on Auto, try "I want to become a cybersecurity analyst": the AI drafts a track (labelled AI-drafted, model named), its new skills are tied to real catalog courses, and the path is built by the same rules as curated ones. Point out the answer check's "Track: AI-drafted" caution. For a goal the catalog can't teach (e.g. "bake sourdough bread") the chart shows every skill as "No course". Picking a curated track, or running without a key, gives the old behaviour: matching courses and a "no structured path" message.
