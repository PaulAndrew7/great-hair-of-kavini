# How Prior works: a plain-language guide

This guide explains the whole project without assuming any technical background. For setup commands see the [README](../README.md); for the technical reasoning see [design.md](design.md).

---

## 1. What Prior is, in one paragraph

Prior is a website that helps a university student answer *"What should I learn next?"* The student types a goal in ordinary words, for example **"I know Python and SQL. Help me move into machine learning."** Prior then shows:

- a short list of real online courses that fit the goal;
- a chart of the skills needed, split into the ones the student already has and the ones they are missing;
- a numbered learning path: which course to take first, second, third;
- a plain explanation of why each course was suggested, and anything to be careful about.

The student can also ask **"What if I already knew Statistics?"** and see how the plan would change.

The courses come from a public list of 6,642 Coursera courses. Everything runs on one computer. There is no AI chatbot and no paid service, and after a one-time setup it works without internet (except for opening the actual course pages).

---

## 2. A tour of the website

The site has two pages, chosen in the top bar: **Discover** (where students use it) and **Evaluation** (which shows how well it works).

### The top bar

- **Prior · University Course Finder** on the left takes you back to Discover.
- On the right, a status label shows whether the system is ready: "6,642 courses · Hybrid search ready" when everything is working, "Keyword search only" if the smart-search part could not load, or "Service offline" if the back end is not running.
- The moon/sun button switches between dark and light colours. Light is best on a projector.

### Discover, step by step

**1. Type a goal.** At the top is a big box: *"What do you want to learn next?"* Type a sentence and press Enter or **Find courses**. Before the first search, three example goals are shown as buttons, and a preview of the three supported subjects (machine learning, data analytics, cloud computing) appears below.

**2. Check "Skills you have".** Prior reads the sentence and pulls out the skills you said you know. For "I know Python and SQL" it shows two black chips: **Python** and **SQL**.
- Press **×** on a chip if it's wrong. Prior then treats that skill as unknown.
- Type in **Add a skill** to add one it missed. Suggestions appear as you type.
- Your edits always win over what Prior guessed. It also understands "don't": "I don't know Python yet" does **not** count Python as known.

**3. Track and filters (optional).**
- **Track** is the subject area. On **Auto**, an AI model drafts a track for your goal: it adapts one of the three hand-made tracks when your goal fits one, or makes a new one (cybersecurity, UX design, React…). The button then reads "Auto: AI-drafted", and the chart carries an **AI-drafted** label. Pick Machine learning, Data analytics or Cloud computing yourself to use the hand-made track exactly as it is.
- **Filters** narrow the course list: **Difficulty** (Beginner, Intermediate, Advanced), **Organization** (e.g. IBM, Google), and **Minimum rating** (4.0, 4.5 or 4.7 and up). A course with no level or no rating is never counted as matching a filter, because we don't know.

**4. Read the results.** The results area has two columns.

**Left: "Courses for this goal".** Up to five courses, ranked. Each shows:
- its title, organization, level and star rating (with how many reviews);
- small coloured squares for the skills it teaches, and "Step 3 of your path" if it is also part of your learning path;
- a one-line prerequisite check, for example **"Missing first: Calculus, Linear Algebra, Statistics."**, "Ready: you have Python.", or **"Prerequisites not verified."** when we honestly don't know;
- a **Why this course** button that opens the Honest Advisor (section 5 below), a short summary from the catalog, a link to the real course page, and feedback buttons.

**Right: the skill chart and the learning path.**

The **skill chart** looks like a periodic table. Each square ("tile") is one skill, with a two-letter symbol (Py = Python, Ml = Machine Learning).
- **Black** tiles: skills you already have.
- **Blue** tiles: skills your goal needs that you don't have yet.
- **Yellow** tiles: foundation skills you need first.
- **Striped** tiles: skills you are pretending to know in a What-If (section 6).
- **Rows** go in learning order: row 1 is the foundations, row 2 builds on row 1, and so on.
- Each tile says which step of the path covers it ("Step 2"), or "No course" if nothing in the catalog could.
- Point at (or tab to) a tile to see what it builds on and why, in a line under the chart.

Above the chart, the **coverage** row shows how many goal skills you have **now** and how many you'd have **after the path**, e.g. "0 of 3" and "3 of 3". This counts course topics, not how good you are at them.

The **learning path** below the chart is a numbered list of real courses in the order to take them. For the example goal it is:

1. *Mathematics for Machine Learning Specialization*: adds Calculus and Linear Algebra
2. *Statistics and Data Analysis with Excel, Part 1*: adds Statistics
3. *Foundations of Machine Learning*: adds Machine Learning and Regression
4. *Structuring Machine Learning Projects*: adds Deep Learning

Each step says what it **builds on** and where that information came from, for example "Builds on Machine Learning (step 3). Source: course description." When the course's own description says something useful, it is quoted, e.g. *"This is also a standalone course for learners who have basic machine learning knowledge."* If some skill can't be covered, a yellow box **"Not covered by this path"** explains why.

At the very bottom, a small grey line records which version of the data was used and how long the answer took (usually 20–30 thousandths of a second).

**5. Special messages.** Prior tells you plainly when something is off:
- if the AI model can't be reached, a grey line says so and Prior falls back to the three hand-made tracks: a goal outside them (e.g. "learn the violin") still gets matching courses, but the chart is replaced by **"No skill chart for this goal"**;
- if the AI proposed a skill no catalog course mainly teaches, the chart says it was **left out**;
- a goal that fits two subjects asks **"Which track did you mean?"**;
- filters that exclude everything say so, with a **Clear filters** button;
- if the back end isn't running, the page says so and shows the command to start it.

### Evaluation

This page shows measured results: how often the suggested courses were actually relevant, how accurate the skill gaps were, whether the learning paths made sense, and how fast it runs. It only displays a saved report. If no report exists yet it says **"Not evaluated yet"** instead of showing made-up numbers. Section 9 explains the results.

---

## 3. What happens when you press "Find courses"

Behind the website is a program called the **back end** (the "service"). The website sends it your goal, your skill chips and your filters, and it sends back everything you see. It does this in seven steps.

1. **Read the goal.** Split the sentence into parts and sort each skill mentioned into "you know it" ("I know Python"), "you don't" ("I don't know SQL") or "you want it" ("help me move into machine learning"). Work out which subject area the goal belongs to.
2. **Apply your filters.** Set aside every course that doesn't match your difficulty, organization or rating choice.
3. **Search** the remaining courses two ways at once and combine the results (section 4).
4. **Work out your skill gap:** the skills the subject needs, minus the ones you have.
5. **Build a learning path** that covers the gap in a sensible order (section 5).
6. **Rank the top courses for you:** among the most relevant results, put first the ones you are ready for and the ones that teach skills you're missing.
7. **Write the explanations** for each course from the facts gathered above.

The whole thing takes about 30 milliseconds.

---

## 4. How the search works

### Where the courses come from

The course list is a public dataset of Coursera courses (from Hugging Face, one of the links in the assignment). It has 6,645 rows with title, organization, description, skills, level and rating. Before using it we **cleaned** it:

- removed 3 exact duplicate courses, leaving **6,642**;
- kept missing information as missing: a course with no rating is "no rating", not zero stars;
- merged different spellings of the same skill ("Python Programming" becomes "Python"), but kept different things separate ("Computer Programming" is not "Python");
- distrusted 196 descriptions that were copied between different courses or didn't match their own title, and stopped using them for search.

### Two kinds of search, combined

- **Keyword search** looks for courses that contain the same words as your goal, a bit like a library catalogue search. It's good at exact names like "Tableau" or "TensorFlow".
- **Meaning search** understands that different words can mean the same thing. It turns every course, and your goal, into a list of numbers that captures meaning (an "embedding"), using a small free language model called MiniLM that runs on the computer. Courses whose numbers are close to your goal's numbers are about similar things. So "renting servers over the internet" finds cloud computing courses even though it never says "cloud".
- The two ranked lists are **merged** with a simple rule (Reciprocal Rank Fusion): a course near the top of either list, or fairly high on both, ends up near the top of the combined list.

If few courses are a close enough match, Prior shows fewer than five (or none) rather than padding the list with poor ones. It never shows a fake "95% match" score, because these numbers don't measure how suitable a course is for you.

---

## 5. How skill gaps and learning paths work

### The skill map

For each of the three supported subjects we wrote down, by hand, the skills it needs and what each skill depends on. For machine learning:

- **Goal skills:** Machine Learning, Regression, Deep Learning.
- **Foundations:** Python, Statistics, Linear Algebra, Calculus.
- **Rules**, each with a written reason, e.g. "Machine Learning needs Python, Statistics and Linear Algebra" and "Deep Learning needs Machine Learning and Calculus".

Your **skill gap** is simply: everything the subject needs, minus what you have. With Python and SQL, you're missing Machine Learning, Regression and Deep Learning (blue) plus Statistics, Linear Algebra and Calculus (yellow).

These rules are our recommendation, based on how universities usually order these topics. They are not official university requirements, and the site labels them "curated guidance".

### Where prerequisite information comes from

Every "you need X first" statement says where it came from:

| Label | Meaning |
|---|---|
| **Course description** | The course's own description says so, and we quote it. (Checked by hand for 8 courses.) |
| **Curated guidance** | It comes from our skill map above. |
| **Prerequisites not verified** | We don't know, and we say so instead of guessing "none". |

### Building the path

The path is built one step at a time, like planning a route:

1. Look at the missing skills you're ready to learn now (their foundations are already covered).
2. Search the *whole* catalog (within your filters) for courses mainly about those skills. A course that only mentions a skill in passing doesn't count.
3. Skip any course whose known prerequisites you won't have yet.
4. Pick the course that covers the most of those skills, preferring relevant, well-rated courses at a sensible level.
5. Mark its skills as covered and repeat, up to five courses.

If something can't be covered (for example your filters exclude every Calculus course), the path stops and tells you why instead of inventing a course or quietly ignoring your filters.

---

## 6. What-If: "What if I already knew…?"

Press any **blue or yellow tile**. Prior recalculates everything as if you already knew that skill, and a striped **What-if** bar appears at the top:

> Treating **Statistics** as known. Your saved profile is unchanged.
> Skills to get: 6 to 5. Path: still 4 courses, 3 swapped.

The path marks what changed: **"New in this what-if"** on new steps, **"Was step 2"** on moved ones, and a **"Dropped in this what-if"** list. If nothing changes it says **"No path change"**.

Knowing Statistics swaps three courses here because Regression depends only on Statistics. Once Statistics is assumed, a calculus course that also teaches Regression becomes the best first step.

Things to know:
- It's a pretend scenario: your real skill chips never change. **Reset simulation** brings the original plan back exactly.
- Knowing more doesn't always shorten the path. Sometimes it's the same, and occasionally one course longer, because the planner picks one step at a time. Prior shows what actually happens.
- It uses exactly the same calculation as a normal search, so the result is what you'd get if you really had that skill.

---

## 7. The Honest Advisor ("Why this course")

Each course's **Why this course** panel has three parts, written from the facts, not by a chatbot:

- **Why this helps:** how it matched your goal (by keywords, by meaning, or both), and which of your missing skills it teaches, with where that information came from (the catalog's skill tags or the course title).
- **Before you start:** what the course expects, where that came from, what you already have and what you're missing.
- **Things to consider:** honest warnings, such as an Advanced course while your foundations are missing, a Beginner course covering things you already know, a rating based on very few reviews, no level stated, a description we didn't trust, or a multi-course programme that is a longer commitment.

It never promises a job, and it never claims that finishing a course means you've mastered a skill.

---

## 8. Feedback

Inside **Why this course**, the student can answer "Was this a good suggestion for you?" with **Relevant**, **Not relevant**, **Too advanced**, **Too basic** or **Already learned**, and optionally add a note. Answers are saved in a small database file on the computer, together with the goal and skills at the time. They are kept for review; they don't secretly change future rankings.

---

## 9. How we know it works (the Evaluation page, simply)

We wrote **18 realistic goals** (6 per subject) before looking at any results. Six are "development" goals, the kind you may look at while adjusting the system; the other twelve were kept aside as a fair final test. (In practice no settings were adjusted after the goals were written.)

For each test goal we took the top 5 courses from keyword search, meaning search and the combined search, mixed them up so the judge couldn't tell which method found which, and marked each course relevant or not, with a reason. The judge was Claude (an AI assistant), and the project author still needs to review those marks.

| On the 12 test goals | Keyword only | Meaning only | Combined (used by the site) |
|---|---|---|---|
| Relevant courses in the top 5 | 63% | **87%** | 75% |
| How early the first relevant course appears (MRR, best = 1) | 0.75 | 0.83 | **0.90** |

In plain words: meaning search finds the most relevant courses overall; the combined search is best at putting a relevant course first. The combined search sometimes gets distracted by keyword matches on common words (for "cloud engineering" it pulled in *data* engineering courses). We report this rather than tweak the system until the test looks better.

Other checks:
- **Skill gaps:** on 9 example students, Prior got the missing-skill list exactly right for 7. It missed "I *studied* calculus" and a bare "networking".
- **Learning paths:** in all 9, every goal skill was covered, no course repeated, and no course came before the skills it needs.
- **Speed:** about 28 milliseconds per answer. Starting the back end takes about 13 seconds.
- **Unusual inputs:** 4 of 5 passed. An empty goal gets a message, an unrelated goal gets no fake path, impossible filters are explained, and "I don't know Python" is respected. The one failure: "work with data in the cloud" went straight to cloud computing instead of asking which subject was meant.

---

## 10. What Prior does *not* do

- Only three subjects (machine learning, data analytics, cloud computing) are curated by hand. Other goals get AI-drafted tracks, which nobody has reviewed and which the evaluation does not measure.
- It uses an AI model only to draft tracks. It isn't a chatbot, and it never lets the model write explanations or choose courses.
- It has no accounts and stores no personal profile beyond anonymous feedback.
- It doesn't know official university prerequisites; only 8 courses have prerequisites taken from their own descriptions.
- The catalog's skill tags are imperfect, so a course is occasionally credited with a skill it only touches on.
- Its test set is small (18 goals, 9 students), and the relevance marks still need a human check.

---

## 11. Running it

In short, you need two programs running: the **back end** (Python, on port 8100) and the **website** (on port 5173). Then open http://localhost:5173. The exact commands are in the [README](../README.md).

## 12. Where things live

| Folder | What's in it |
|---|---|
| `backend/app/` | The back end: reading goals, searching, skill gaps, paths, explanations, feedback |
| `backend/scripts/` | One-off jobs: download the data and model, clean the data, build the search index, run the evaluation |
| `frontend/src/` | The website: the Discover and Evaluation pages and their parts |
| `data/raw/` | The original course file, untouched |
| `data/processed/` | The cleaned courses and the search index |
| `data/rules/` | The hand-written skill map and prerequisite notes |
| `data/evaluation/` | The test goals, example students, relevance marks and the latest report |
| `docs/` | This guide, the architecture diagram, design notes, evaluation write-up, demo script and screenshots |

## 13. Glossary

| Term | Meaning |
|---|---|
| **Back end / service** | The program that does the work; the website asks it questions. |
| **API** | The set of questions the website can send to the back end (`/recommend`, `/feedback` and so on). |
| **Track** | One of the three supported subject areas. |
| **Goal skill / foundation** | A skill the subject is about (blue) / a skill needed before it (yellow). |
| **Skill gap** | The skills a subject needs that you don't have yet. |
| **Prerequisite** | Something you should know before starting a course. |
| **Keyword search (BM25)** | Finds courses sharing words with your goal, favouring rarer words. |
| **Embedding** | A list of numbers representing the meaning of a text, so similar meanings get similar numbers. |
| **MiniLM** | The small, free language model that makes the embeddings. It runs locally. |
| **Reciprocal Rank Fusion (RRF)** | The rule that merges the keyword and meaning rankings into one list. |
| **Precision@5** | Of the top 5 results, the fraction that were relevant. |
| **MRR@5** | How early the first relevant result appears: 1 if first, 0.5 if second, and so on; 0 if none in the top 5. |
| **Development / test goals** | Goals used while building vs goals kept aside for a fair final check. |
| **Keyword-only mode** | A fallback if the meaning-search model can't load. Clearly labelled, never disguised. |
| **What-If** | A pretend "if I already knew X" scenario that doesn't change your real profile. |
| **Coverage** | How many of the subject's goal skills are covered, now and after the path. A count of topics, not a grade. |
