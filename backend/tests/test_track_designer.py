"""AI-drafted tracks, with a fake chat client: validation, catalog grounding, caching and fallback. No network."""
import pytest
from fastapi.testclient import TestClient

from app import config
from app import main as main_module
from app.track_designer import LLMError, TrackDesigner, make_abbr

CYBER = {
    "label": "Cybersecurity analyst",
    "skills": [
        {"name": "networking", "goal": False, "requires": []},
        {"name": "Network Security", "goal": True, "requires": ["Networking"], "keywords": ["network security"],
         "why": "Securing a network starts with how it works."},
        {"name": "Penetration Testing", "goal": True, "requires": ["Network Security", "Quantum Lockpicking"],
         "keywords": ["penetration testing", "ethical hacking"]},
    ],
}


class FakeClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def chat_json(self, system, user):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    config.FEEDBACK_DB = tmp_path_factory.mktemp("fb") / "feedback.sqlite3"
    with TestClient(main_module.app) as c:
        yield c


def designer(reply) -> tuple[TrackDesigner, FakeClient]:
    s = main_module.state
    fake = FakeClient(reply)
    rec = s.recommender
    return TrackDesigner(s.catalog, s.skills, rec.prereqs, rec.path_ctx, s.engine.embedder, fake), fake


@pytest.fixture
def use_designer(client):
    rec = main_module.state.recommender

    def install(reply):
        d, fake = designer(reply)
        rec.designer = d
        return fake

    yield install
    rec.designer = None


def test_draft_reuses_curated_skills_and_grounds_new_ones(client):
    d, _ = designer(CYBER)
    draft = d.build(CYBER, None)
    sk = draft.skills
    assert "Networking" in draft.foundations  # lower-case name mapped to the curated skill
    assert draft.targets == ["Network Security", "Penetration Testing"]
    assert draft.new_skills == ["Network Security", "Penetration Testing"]
    assert sk.deps["Penetration Testing"] == ["Network Security"]  # the unknown requirement is ignored
    assert sk.dep_reason["Network Security"].startswith("Securing")
    assert sk.origin["Network Security"] == "ai" and sk.origin["Networking"] == "curated"
    assert sk.period["Penetration Testing"] > sk.period["Network Security"] > sk.period["Networking"]
    assert len(draft.ctx.courses_for("Network Security")) > 20
    # Evidence lives on the per-track view; the shared catalog records are untouched.
    pos = draft.ctx.courses_for("Network Security")[0]
    assert any(ev["skill"] == "Network Security" for ev in draft.ctx.course(pos)["track_skills"])
    assert not any(ev["skill"] == "Network Security" for ev in main_module.state.catalog.courses[pos]["track_skills"])
    assert "Network Security" not in main_module.state.skills.skills
    assert sk.canonical("network security") == "Network Security"
    assert "Network Security" in sk.parse_goal("I already know network security").known


def test_cycle_edge_is_dropped_and_reported(client):
    raw = {"label": "Loop", "skills": [
        {"name": "Network Security", "goal": True, "requires": ["Penetration Testing"]},
        {"name": "Penetration Testing", "goal": True, "requires": ["Network Security"]},
    ]}
    d, _ = designer(raw)
    draft = d.build(raw, None)
    assert draft.skills.deps["Network Security"] == ["Penetration Testing"]
    assert draft.skills.deps["Penetration Testing"] == []
    assert any("cycle" in n for n in draft.notes)


def test_unteachable_skill_is_left_out_and_dependents_inherit(client):
    raw = {"label": "Security", "skills": [
        {"name": "Network Security", "goal": False, "requires": []},
        {"name": "Quantum Lockpicking", "goal": False, "requires": ["Network Security"]},
        {"name": "Penetration Testing", "goal": True, "requires": ["Quantum Lockpicking"]},
    ]}
    d, _ = designer(raw)
    draft = d.build(raw, None)
    assert draft.left_out == ["Quantum Lockpicking"] and draft.unteachable == []
    assert "Quantum Lockpicking" not in draft.skills.skills
    assert draft.skills.deps["Penetration Testing"] == ["Network Security"]
    assert any("Left out Quantum Lockpicking" in n for n in draft.notes)


def test_goal_outside_the_catalog_keeps_the_draft_and_reports_it(client):
    raw = {"label": "Sourdough", "skills": [
        {"name": "Sourdough Starters", "goal": False, "requires": []},
        {"name": "Loaf Scoring", "goal": True, "requires": ["Sourdough Starters"]},
    ]}
    d, _ = designer(raw)
    draft = d.build(raw, None)
    assert draft.left_out == [] and draft.unteachable == ["Sourdough Starters", "Loaf Scoring"]


def test_targets_fall_back_to_skills_nothing_builds_on(client):
    raw = {"label": "Security", "skills": [
        {"name": "Network Security", "requires": []},
        {"name": "Penetration Testing", "requires": ["Network Security"]},
    ]}
    d, _ = designer(raw)
    assert d.build(raw, None).targets == ["Penetration Testing"]


@pytest.mark.parametrize("raw", [{"skills": "none"}, {"skills": [{"name": ""}, {"name": 7}]}, ["not", "a", "dict"]])
def test_unusable_answers_are_rejected(client, raw):
    d, _ = designer(raw)
    with pytest.raises(LLMError):
        d.build(raw, None)


def test_abbreviations_are_unique():
    taken = {"Ns"}
    assert make_abbr("Network Security", taken) == "Ne"
    assert make_abbr("React", set()) == "Re"


def test_auto_uses_the_drafted_track_and_what_if_reuses_it(client, use_designer):
    fake = use_designer(CYBER)
    goal = "I want to become a cybersecurity analyst"
    r = client.post("/recommend", json={"goal": goal})
    assert r.status_code == 200, r.text
    d = r.json()
    p = d["profile"]
    assert p["track_id"] == "custom" and p["track_status"] == "generated" and p["track_label"] == "Cybersecurity analyst"
    assert p["ai_track"]["model"] and p["ai_track"]["base_track"] is None
    tiles = {t["skill"]: t for t in d["skill_gap"]["tiles"]}
    assert tiles["Penetration Testing"]["origin"] == "ai" and tiles["Networking"]["origin"] == "curated"
    assert d["learning_path"]["available"] and d["learning_path"]["steps"]
    assert d["evaluation"]["track"]["confidence"] == "drafted"
    assert d["evaluation"]["path"]["prerequisite_violations"] == 0
    assert d["evaluation"]["retrieval"]["extrapolated"] is True
    sim = client.post("/recommend", json={"goal": goal, "simulated_skills": ["Networking"]}).json()
    assert sim["profile"]["track_label"] == "Cybersecurity analyst"
    assert fake.calls == 1  # cached per goal


def test_detected_track_is_passed_as_the_base(client, use_designer):
    fake = use_designer(CYBER)
    client.post("/recommend", json={"goal": "Help me move into machine learning."})
    assert fake.calls == 1


def test_a_chosen_track_never_calls_the_model(client, use_designer):
    fake = use_designer(CYBER)
    d = client.post("/recommend", json={"goal": "I want to become a cybersecurity analyst",
                                         "goal_track": "cloud_computing"}).json()
    assert fake.calls == 0 and d["profile"]["track_status"] == "selected" and d["profile"]["ai_track"] is None


def test_gateway_failure_falls_back_to_curated_rules(client, use_designer):
    use_designer(LLMError("gateway unreachable (ConnectError)"))
    d = client.post("/recommend", json={"goal": "I know Python and SQL. Help me move into machine learning."}).json()
    assert d["profile"]["track_status"] == "detected" and d["profile"]["track_id"] == "machine_learning"
    assert any(w["code"] == "ai_track_unavailable" for w in d["warnings"])
    assert d["skill_gap"]["available"]
