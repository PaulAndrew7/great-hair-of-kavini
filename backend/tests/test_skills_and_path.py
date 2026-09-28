import numpy as np
import pytest

from app.catalog import Catalog
from app.learning_path import PathContext, build_path
from app.prerequisites import PrereqModel
from app.skills import CycleError, SkillModel

GOALS = {
    "version": "test",
    "skills": {
        "Python": {"abbr": "Py", "title_patterns": ["python"]},
        "Statistics": {"abbr": "St", "title_patterns": ["statistics"]},
        "Machine Learning": {"abbr": "Ml", "title_patterns": ["machine learning"]},
        "Deep Learning": {"abbr": "Dl", "title_patterns": ["deep learning"]},
    },
    "dependencies": [
        {"skill": "Machine Learning", "requires": ["Python", "Statistics"]},
        {"skill": "Deep Learning", "requires": ["Machine Learning"]},
    ],
    "tracks": {"machine_learning": {"label": "ML", "target_skills": ["Machine Learning", "Deep Learning"],
                                    "detect": ["machine learning"], "query_hint": "machine learning"}},
}


def course(cid, title, difficulty="Beginner", rating=4.6):
    return {"course_id": cid, "title": title, "skills": [], "difficulty": difficulty, "rating": rating,
            "organization": "Org", "description": None, "description_quality": "Missing"}


def make_ctx(courses, reviewed=None):
    cat = Catalog(courses=courses, embeddings=np.zeros((len(courses), 4), dtype=np.float32),
                  manifest={"data_version": "t"}, goal_skills=GOALS)
    skills = SkillModel(GOALS, {}, [])
    return PathContext(cat, skills, PrereqModel(skills, reviewed or {}), None), cat, skills


def run(ctx, known, eligible=None):
    n = len(ctx.catalog.courses)
    mask = np.ones(n, dtype=bool) if eligible is None else eligible
    return build_path(ctx, "machine_learning", set(known), mask, None, False, False)


def test_cycles_are_rejected():
    bad = {**GOALS, "dependencies": [{"skill": "Python", "requires": ["Statistics"]},
                                     {"skill": "Statistics", "requires": ["Python"]}]}
    with pytest.raises(CycleError):
        SkillModel(bad, {}, [])


def test_negation_and_corrections():
    skills = SkillModel(GOALS, {}, [])
    parse = skills.parse_goal("I know Python but I don't know statistics. Help me with machine learning.")
    assert parse.known == ["Python"] and parse.negated == ["Statistics"] and "Machine Learning" in parse.mentioned
    assert skills.parse_goal("I don't know Python").known == []


def test_path_respects_dependency_order_and_covers_everything():
    ctx, _, _ = make_ctx([course("c1", "Python basics"), course("c2", "Statistics 101"),
                          course("c3", "Machine Learning"), course("c4", "Deep Learning", "Intermediate")])
    path = run(ctx, [])
    order = [ctx.catalog.courses[s["pos"]]["course_id"] for s in path["steps"]]
    assert order.index("c3") > order.index("c1") and order.index("c3") > order.index("c2")
    assert order[-1] == "c4" and path["complete"] and len(set(order)) == len(order)


def test_multi_skill_course_preferred_and_no_duplicates():
    ctx, _, _ = make_ctx([course("c1", "Python basics"), course("c2", "Statistics 101"),
                          course("c9", "Python and Statistics bootcamp"), course("c3", "Machine Learning"),
                          course("c4", "Deep Learning")])
    path = run(ctx, [])
    first = ctx.catalog.courses[path["steps"][0]["pos"]]
    assert first["course_id"] == "c9" and set(path["steps"][0]["new_skills"]) == {"Python", "Statistics"}


def test_missing_foundation_course_leaves_honest_unresolved_gaps():
    ctx, _, _ = make_ctx([course("c1", "Python basics"), course("c3", "Machine Learning"), course("c4", "Deep Learning")])
    path = run(ctx, [])
    reasons = {u["skill"]: u["reason"] for u in path["unresolved"]}
    assert "No course" in reasons["Statistics"]
    assert "Waits on" in reasons["Machine Learning"] and not path["complete"]
    assert all(ctx.catalog.courses[s["pos"]]["course_id"] != "c3" for s in path["steps"])  # never scheduled early


def test_already_covered_track_needs_no_path():
    ctx, _, _ = make_ctx([course("c1", "Python basics")])
    path = run(ctx, ["Python", "Statistics", "Machine Learning", "Deep Learning"])
    assert path["steps"] == [] and path["complete"]


def test_filters_that_exclude_foundations_are_reported():
    ctx, _, _ = make_ctx([course("c1", "Python basics"), course("c2", "Statistics 101"), course("c3", "Machine Learning")])
    eligible = np.array([True, False, True])
    path = build_path(ctx, "machine_learning", set(), eligible, None, False, True)
    reasons = {u["skill"]: u["reason"] for u in path["unresolved"]}
    assert reasons["Statistics"].endswith("with the current filters.")


def test_explicit_prerequisite_blocks_scheduling():
    reviewed = {"c3": {"course_id": "c3", "requires": ["Python", "Statistics", "Deep Learning"], "evidence": "x"}}
    ctx, _, _ = make_ctx([course("c1", "Python basics"), course("c2", "Statistics 101"), course("c3", "Machine Learning")],
                         reviewed)
    path = run(ctx, [])
    assert "c3" not in [ctx.catalog.courses[s["pos"]]["course_id"] for s in path["steps"]]
