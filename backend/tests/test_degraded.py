"""Keyword-only degraded mode: a valid catalog without the embedding model is served, and labelled as such."""
import pytest
from fastapi.testclient import TestClient

from app import config
from app import main as main_module


class MissingModel:
    def __init__(self):
        raise OSError("model files not found in the local cache")


@pytest.fixture(scope="module")
def client(tmp_path_factory, monkeypatch_module):
    monkeypatch_module.setattr(config, "FEEDBACK_DB", tmp_path_factory.mktemp("fb") / "feedback.sqlite3")
    monkeypatch_module.setattr(main_module, "Embedder", MissingModel)
    with TestClient(main_module.app) as c:
        yield c


@pytest.fixture(scope="module")
def monkeypatch_module():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


def test_health_reports_degraded_mode(client):
    h = client.get("/health").json()
    assert h["status"] == "degraded" and h["mode"] == "keyword_only"
    assert h["model"]["loaded"] is False and "not found" in h["model"]["error"]


def test_recommend_still_works_and_says_keyword_only(client):
    r = client.post("/recommend", json={"goal": "I know Python and SQL. Help me move into machine learning."}).json()
    assert r["mode"] == "keyword_only"
    assert any(w["code"] == "keyword_only" for w in r["warnings"])
    assert r["courses"] and all(c["retrieval"]["semantic_rank"] is None for c in r["courses"])
    assert r["skill_gap"]["available"] and r["learning_path"]["steps"]


def test_semantic_search_is_refused_not_faked(client):
    assert client.post("/search", json={"query": "cloud security", "mode": "semantic"}).status_code == 503
    assert client.post("/search", json={"query": "cloud security", "mode": "hybrid"}).status_code == 503
    assert client.post("/search", json={"query": "cloud security", "mode": "bm25"}).status_code == 200


def test_keyword_only_confidence_is_the_base_rate_not_a_ranking_signal(client):
    r = client.post("/recommend", json={"goal": "I want to learn cloud computing from the basics."}).json()
    confs = {c["retrieval"]["confidence"] for c in r["courses"]}
    assert len(confs) == 1  # no semantic signal: every result gets the same labelled base rate
    assert r["evaluation"]["calibration"]["auc"] is None and r["evaluation"]["retrieval"]["channel_agreement"] is None
