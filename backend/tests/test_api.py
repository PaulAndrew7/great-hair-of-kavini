"""Service-level checks against the real processed catalog (run prepare_data.py and build_index.py first)."""
import shutil

import pytest
from fastapi.testclient import TestClient

from app import config
from app import main as main_module

DEMO = "I know Python and SQL. Help me move into machine learning."


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("fb") / "feedback.sqlite3"
    config.FEEDBACK_DB = db
    with TestClient(main_module.app) as c:
        yield c


def post(client, **body):
    r = client.post("/recommend", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_health_reports_real_catalog(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["mode"] == "hybrid" and h["course_count"] > 6000


def test_demo_profile_gaps_and_path_are_consistent(client):
    d = post(client, goal=DEMO)
    p = d["profile"]
    assert p["track_id"] == "machine_learning" and set(p["confirmed_skills"]) == {"Python", "SQL"}
    gap = d["skill_gap"]
    assert gap["available"] and "Machine Learning" in gap["missing_targets"]
    tiles = {t["skill"]: t for t in gap["tiles"]}
    assert tiles["Python"]["state"] == "known" and tiles["Statistics"]["state"] == "missing"
    ids = [s["course"]["course_id"] for s in d["learning_path"]["steps"]]
    assert len(ids) == len(set(ids)) <= config.MAX_PATH_STEPS
    covered = set(p["effective_skills"])
    for step in d["learning_path"]["steps"]:  # modelled prerequisites hold at every step
        assert step["prerequisites"]["status"] != "unmet"
        assert all(r in covered for r in step["prerequisites"]["required"])
        covered |= set(step["new_skills"])
    courses = d["courses"]
    assert 1 <= len(courses) <= 5 and len({c["course_id"] for c in courses}) == len(courses)
    assert all(c["advisor"]["why"] and c["advisor"]["before"] for c in courses)


def test_what_if_equals_normal_request_with_same_effective_skills(client):
    sim = post(client, goal=DEMO, simulated_skills=["Statistics"])
    real = post(client, goal=DEMO, known_skills=["Statistics"])
    assert sim["is_simulation"] and not real["is_simulation"]
    assert sim["profile"]["confirmed_skills"] == ["Python", "SQL"]  # simulation never leaks into the profile
    assert [s["course"]["course_id"] for s in sim["learning_path"]["steps"]] == \
           [s["course"]["course_id"] for s in real["learning_path"]["steps"]]
    assert [c["course_id"] for c in sim["courses"]] == [c["course_id"] for c in real["courses"]]
    base = post(client, goal=DEMO)
    assert base["profile"]["simulated_skills"] == [] and base["skill_gap"]["tiles"] != sim["skill_gap"]["tiles"]


def test_negated_and_excluded_skills_are_not_known(client):
    d = post(client, goal="I don't know Python. I want to learn machine learning.")
    assert "Python" not in d["profile"]["confirmed_skills"] and "Python" in d["profile"]["negated_skills"]
    d = post(client, goal=DEMO, excluded_skills=["SQL"])
    assert d["profile"]["confirmed_skills"] == ["Python"]


def test_filters_hold_and_unknowns_do_not_satisfy_them(client):
    d = post(client, goal=DEMO, filters={"difficulty": "Beginner", "min_rating": 4.5})
    for c in d["courses"] + [s["course"] for s in d["learning_path"]["steps"]]:
        assert c["difficulty"] == "Beginner" and c["rating"] is not None and c["rating"] >= 4.5


def test_impossible_filter_returns_honest_empty_state(client):
    d = post(client, goal=DEMO, filters={"organization": "No Such University"})
    assert d["courses"] == [] and any(w["code"] == "filters_excluded" for w in d["warnings"])
    assert d["eligible_count"] == 0


def test_unrelated_goal_has_no_fabricated_path(client):
    d = post(client, goal="teach me medieval european history")
    assert d["profile"]["track_status"] == "unsupported"
    assert not d["skill_gap"]["available"] and not d["learning_path"]["available"]


def test_ambiguous_goal_asks_for_a_track(client):
    d = post(client, goal="I want to learn data science from the basics")
    assert d["profile"]["track_status"] == "ambiguous" and len(d["profile"]["track_candidates"]) == 2
    d = post(client, goal="I want to learn data science from the basics", goal_track="data_analytics")
    assert d["skill_gap"]["available"] and d["profile"]["track_status"] == "selected"


def test_validation_messages(client):
    r = client.post("/recommend", json={"goal": "   "})
    assert r.status_code == 422 and r.json()["problems"][0]["field"] == "goal"
    r = client.post("/recommend", json={"goal": "x", "top_k": 50})
    assert r.status_code == 422
    r = client.post("/recommend", json={"goal": "x", "filters": {"min_rating": 9}})
    assert r.status_code == 422


def test_search_modes_share_the_engine(client):
    for mode in ("bm25", "semantic", "hybrid"):
        r = client.post("/search", json={"query": "introduction to statistics", "mode": mode, "top_k": 5})
        assert r.status_code == 200
        ids = [x["course"]["course_id"] for x in r.json()["results"]]
        assert len(ids) == len(set(ids)) and len(ids) > 0
    a = client.post("/search", json={"query": "cloud security", "mode": "hybrid"}).json()
    b = client.post("/search", json={"query": "cloud security", "mode": "hybrid"}).json()
    assert [x["course"]["course_id"] for x in a["results"]] == [x["course"]["course_id"] for x in b["results"]]


def test_feedback_persists_and_validates(client):
    course_id = post(client, goal=DEMO)["courses"][0]["course_id"]
    r = client.post("/feedback", json={"course_id": course_id, "label": "too_advanced", "goal": DEMO})
    assert r.status_code == 200 and r.json()["feedback_id"] >= 1
    assert client.post("/feedback", json={"course_id": "cdeadbeef00", "label": "relevant"}).status_code == 422
    assert client.post("/feedback", json={"course_id": course_id, "label": "love_it"}).status_code == 422
    from app.feedback import FeedbackStore
    assert FeedbackStore(config.FEEDBACK_DB).counts().get("too_advanced") == 1  # survives a new connection


def test_misaligned_artifacts_are_refused(tmp_path, monkeypatch):
    from app import catalog as catalog_module
    for name in ("manifest.json", "courses.json", "course_ids.json", "embeddings.npy"):
        shutil.copy(config.PROCESSED_DIR / name, tmp_path / name)
    (tmp_path / "course_ids.json").write_text('["c0"]', encoding="utf-8")
    monkeypatch.setattr(config, "MANIFEST_JSON", tmp_path / "manifest.json")
    monkeypatch.setattr(config, "COURSES_JSON", tmp_path / "courses.json")
    monkeypatch.setattr(config, "COURSE_IDS_JSON", tmp_path / "course_ids.json")
    monkeypatch.setattr(config, "EMBEDDINGS_NPY", tmp_path / "embeddings.npy")
    with pytest.raises(catalog_module.CatalogError):
        catalog_module.load_catalog()


def test_every_answer_carries_its_own_evaluation(client):
    d = post(client, goal="I want to learn GenAI", known_skills=["Python", "SQL"])
    assert d["profile"]["confirmed_skills"] == ["Python", "SQL"]  # typed skills survive a goal the parser can't place
    ev = d["evaluation"]
    for c in d["courses"]:
        r = c["retrieval"]
        assert 0 < r["confidence"] < 1 and r["confidence_band"] in ("high", "medium", "low")
        assert r["judged_relevant"] is None  # not a labelled query: nothing is presented as measured
    assert ev["ground_truth"] is None and ev["calibration"]["labels"] > 100
    assert ev["retrieval"]["expected_relevant"] == pytest.approx(sum(c["retrieval"]["confidence"] for c in d["courses"]), abs=0.01)
    assert ev["track"]["status"] == "unsupported" and ev["path"] is None
    assert ev["retrieval"]["extrapolated"] and any("extrapolated" in n for n in ev["notes"])
    assert ev["reference"]["precision_at_5"] is not None


def test_labelled_query_is_scored_against_its_labels(client):
    d = post(client, goal=DEMO)
    gt = d["evaluation"]["ground_truth"]
    assert gt["query_id"] == "ml-d1" and gt["judged"] <= gt["shown"] == len(d["courses"])
    assert gt["relevant"] == sum(1 for c in d["courses"] if c["retrieval"]["judged_relevant"])
    assert d["evaluation"]["skill_gap"]["profile_id"] == "ml-p1"  # frozen profile with no chip edits
    assert d["evaluation"]["track"]["confidence"] == "high" and not d["evaluation"]["retrieval"]["extrapolated"]
    path = d["evaluation"]["path"]
    assert path["prerequisite_violations"] == 0 and path["duplicates"] == 0
    assert all(s["match"]["skill_similarity"] is not None for s in d["learning_path"]["steps"])


def test_typed_skill_named_in_goal_stays_explicit(client):
    d = post(client, goal=DEMO, known_skills=["Python"])
    assert "Python" not in d["profile"]["inferred_skills"] and "SQL" in d["profile"]["inferred_skills"]
    assert d["evaluation"]["skill_gap"]["profile_id"] == "ml-p1"  # same resulting skills as the frozen profile
    d = post(client, goal=DEMO, known_skills=["Statistics"])
    assert d["evaluation"]["skill_gap"] is None  # different skills: the profile's expected gap no longer applies
    d = post(client, goal=DEMO, simulated_skills=["Statistics"])
    assert d["evaluation"]["skill_gap"] is None  # a what-if gap is not the labelled profile's gap
