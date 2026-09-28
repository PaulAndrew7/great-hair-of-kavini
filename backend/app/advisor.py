"""Honest Advisor: template sentences built only from the recommendation's own evidence."""
from __future__ import annotations

from typing import Any

from .search import Hit


def _join(items: list[str]) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def explain(
    course: dict[str, Any],
    hit: Hit,
    prereq: dict[str, Any],
    gap: dict[str, Any] | None,
    effective: set[str],
    simulated: set[str],
    path_step: int | None,
    beginner: bool,
) -> dict[str, list[str]]:
    why: list[str] = []
    before: list[str] = []
    consider: list[str] = []
    taught = {ev["skill"]: ev for ev in course["track_skills"] if ev.get("strength", "primary") == "primary"}
    listed = [ev["skill"] for ev in course["track_skills"] if ev.get("strength") == "listed"]

    # Why this helps ------------------------------------------------------------
    if hit.bm25_rank and hit.semantic_rank:
        terms = _join([f"'{t}'" for t in hit.matched_terms[:3]])
        why.append(f"Matches your goal by keyword ({terms}) and by meaning.")
    elif hit.bm25_rank:
        why.append(f"Matches your goal by keyword: {_join([repr(t) for t in hit.matched_terms[:3]])}.")
    elif hit.semantic_rank:
        why.append("Close in meaning to your goal, although it shares no exact keywords with it.")
    if gap:
        fills_targets = [s for s in gap["missing_targets"] if s in taught]
        fills_support = [s for s in gap["missing_supporting"] if s in taught]
        for skills, role in ((fills_targets, "a goal skill you are missing"), (fills_support, "a foundation you still need")):
            for skill in skills:
                source = "its catalog skill tags" if taught[skill]["source"] == "catalog tag" else "its title"
                why.append(f"Teaches {skill}, {role} (from {source}).")
        passing = [s for s in listed if s in gap["missing"]]
        if passing:
            why.append(f"Also tags {_join(passing)}, but is not mainly about {'it' if len(passing) == 1 else 'them'}.")
    if path_step:
        why.append(f"Also step {path_step} of your learning path.")

    # Before you start ----------------------------------------------------------
    if prereq["status"] == "unknown":
        before.append("Prerequisites not verified: the catalog does not state them and no curated rule covers this course.")
    else:
        source = prereq["source"]
        if not prereq["required"] and source == "course description":
            before.append("The course description says no prior skills are needed.")
            if prereq["evidence"]:
                before.append(f"Catalog text: “{prereq['evidence']}”")
        elif not prereq["required"]:
            before.append("No prior skills are modelled for this course (curated guidance; the course page itself was not checked).")
        else:
            have = [s for s in prereq["required"] if s in effective]
            label = "The course description asks for" if source == "course description" else "Curated guidance puts these first:"
            before.append(f"{label} {_join(prereq['required'])}.")
            if prereq["evidence"]:
                before.append(f"Catalog text: “{prereq['evidence']}”")
            if have:
                sim = [s for s in have if s in simulated]
                real = [s for s in have if s not in simulated]
                if real:
                    before.append(f"You have {_join(real)}.")
                if sim:
                    before.append(f"You would have {_join(sim)} in this what-if.")
            if prereq["missing"]:
                before.append(f"You are missing {_join(prereq['missing'])}; take {'it' if len(prereq['missing']) == 1 else 'them'} first or expect a steeper start.")

    # Things to consider ----------------------------------------------------------
    difficulty = course["difficulty"]
    if difficulty == "Advanced" and (beginner or (gap and gap["missing_supporting"])):
        consider.append("Listed as Advanced while some foundations in your profile are still missing.")
    if difficulty == "Beginner" and taught and all(s in effective for s in taught):
        consider.append("Beginner level, and you already have every tracked skill it teaches; it may be review.")
    elif taught and all(s in effective for s in taught) and len(taught) > 0:
        consider.append(f"Its tracked skills ({_join(list(taught))}) are ones you already have.")
    if difficulty == "Unknown":
        consider.append("The catalog does not state a difficulty level.")
    if course["rating"] is None:
        consider.append("No rating in the catalog.")
    elif course["num_reviews"] is not None and course["num_reviews"] < 20:
        consider.append(f"Rated {course['rating']:.1f} from only {course['num_reviews']} reviews.")
    elif course["rating"] < 4.3:
        consider.append(f"Rated {course['rating']:.1f}, lower than most courses in this catalog.")
    if course["description_quality"] == "Suspect":
        consider.append("The catalog description may belong to another course, so it was not used for matching.")
    elif course["description_quality"] == "Missing":
        consider.append("The catalog has no description for this course.")
    if not course["skills"]:
        consider.append("No skill tags in the catalog; skills were read from the title only.")
    if course["course_type"] in ("Specialization", "Professional Certificate"):
        detail = f" ({course['structure_text']})" if course.get("structure_text") else ""
        consider.append(f"A {course['course_type']}{detail}: a series of courses, a longer commitment.")
    return {"why": why, "before": before, "consider": consider}
