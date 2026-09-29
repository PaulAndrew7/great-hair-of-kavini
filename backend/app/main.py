"""FastAPI service: routes, startup, health."""
from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .catalog import CatalogError, load_catalog
from .feedback import FeedbackStore
from .prerequisites import PrereqModel, load_reviewed
from .recommend import Recommender, card, retrieval
from .schemas import (CatalogResponse, FeedbackRequest, FeedbackResponse, HealthResponse, RecommendRequest,
                      RecommendResponse, SearchRequest, SearchResponse)
from .search import Embedder, Filters, SearchEngine
from .skills import SkillModel
from .track_designer import GatewayClient, TrackDesigner

log = logging.getLogger("prior")


class State:
    catalog = None
    engine: SearchEngine | None = None
    recommender: Recommender | None = None
    skills: SkillModel | None = None
    feedback: FeedbackStore | None = None
    error: str | None = None
    model_error: str | None = None
    warnings: list[str] = []
    started_ms: float = 0.0


state = State()


def startup() -> None:
    t0 = time.perf_counter()
    state.feedback = FeedbackStore(config.FEEDBACK_DB)
    try:
        catalog = load_catalog()
    except CatalogError as exc:
        state.error = str(exc)
        log.error("catalog unavailable: %s", exc)
        return
    aliases = json.loads(config.SKILL_ALIASES_JSON.read_text(encoding="utf-8"))["aliases"]
    observed = [label for c in catalog.courses for label in c["skills"]]
    skills = SkillModel(catalog.goal_skills, aliases, observed)
    embedder = None
    try:
        embedder = Embedder()
    except Exception as exc:  # model files absent or unreadable: explicit keyword-only mode
        state.model_error = f"{type(exc).__name__}: {exc}"
        log.warning("embedding model unavailable, keyword-only mode: %s", exc)
    engine = SearchEngine(catalog, embedder)
    state.catalog, state.engine, state.skills = catalog, engine, skills
    reviewed, problems = {}, []
    for cid, entry in load_reviewed().items():
        unknown = [s for s in entry["requires"] if s not in skills.skills]
        if catalog.get(cid) is None or unknown:
            problems.append(f"course_prerequisites.json entry {cid} ignored: "
                            + ("unknown course_id" if catalog.get(cid) is None else "unknown skills " + ", ".join(unknown)))
            continue
        reviewed[cid] = entry
    state.recommender = Recommender(catalog, engine, skills, PrereqModel(skills, reviewed))
    if config.LLM_ENABLED:
        rec = state.recommender
        rec.designer = TrackDesigner(catalog, skills, rec.prereqs, rec.path_ctx, embedder,
                                     GatewayClient(config.LLM_URL, config.LLM_KEY, config.LLM_TIMEOUT_S))
    state.warnings = list(catalog.warnings) + problems
    state.started_ms = round((time.perf_counter() - t0) * 1000, 1)
    log.info("ready in %.0f ms, mode=%s, courses=%d", state.started_ms, engine.mode, len(catalog.courses))


@asynccontextmanager
async def lifespan(_: FastAPI):
    startup()
    yield


app = FastAPI(title="Prior: University Course Finder", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    problems = []
    for err in exc.errors():
        where = ".".join(str(p) for p in err["loc"] if p != "body")
        message = err["msg"].removeprefix("Value error, ")
        problems.append({"field": where or "body", "message": message})
    return JSONResponse(status_code=422, content={"detail": "Invalid request.", "problems": problems})


def ready() -> Recommender:
    if state.recommender is None:
        raise HTTPException(status_code=503, detail=state.error or "The service is still starting.")
    return state.recommender


@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, Any]:
    if state.catalog is None:
        return {"status": "unavailable", "mode": None, "data_version": None, "course_count": 0, "model": None,
                "message": state.error or "Starting.", "warnings": []}
    engine = state.engine
    degraded = engine.mode == "keyword_only"
    return {
        "status": "degraded" if degraded else "ok",
        "mode": engine.mode,
        "data_version": state.catalog.data_version,
        "course_count": len(state.catalog.courses),
        "model": {"name": config.MODEL_NAME, "revision": config.MODEL_REVISION[:12], "loaded": not degraded,
                  "error": state.model_error},
        # Configured, not probed: /health never waits on the gateway.
        "llm": {"enabled": state.recommender is not None and state.recommender.designer is not None,
                "model": config.LLM_MODEL_LABEL, "gateway": config.LLM_URL},
        "message": "Keyword-only mode: the embedding model could not be loaded." if degraded
        else f"Ready. Hybrid retrieval over {len(state.catalog.courses):,} courses.",
        "warnings": state.warnings,
    }


@app.get("/catalog", response_model=CatalogResponse)
def catalog_info() -> dict[str, Any]:
    ready()
    skills, catalog = state.skills, state.catalog
    tracks = []
    for tid, t in skills.tracks.items():
        required = skills.closure(t["target_skills"])
        tracks.append({"id": tid, "label": t["label"], "target_skills": t["target_skills"],
                       "supporting_skills": skills.ordered(required - set(t["target_skills"]))})
    return {
        "data_version": catalog.data_version,
        "rules_version": skills.version,
        "course_count": len(catalog.courses),
        "tracks": tracks,
        "track_skills": [
            {"skill": name, "abbr": spec["abbr"], "period": skills.period[name], "requires": skills.deps.get(name, []),
             "reason": skills.dep_reason.get(name), "course_count": len(catalog.skill_courses.get(name, []))}
            for name, spec in skills.skills.items()
        ],
        "skills": sorted(set(skills.skills) | {"Git", "R", "Java", "JavaScript", "TensorFlow", "PyTorch"}),
        "difficulties": ["Beginner", "Intermediate", "Advanced"],
        "organizations": [{"name": n, "count": c} for n, c in catalog.organizations],
        "source": catalog.manifest["source"],
    }


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> dict[str, Any]:
    return ready().recommend(req)


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest) -> dict[str, Any]:
    ready()
    t0 = time.perf_counter()
    filters = Filters(req.filters.difficulty, req.filters.organization, req.filters.min_rating)
    try:
        hits, eligible = state.engine.search(req.query, req.mode, filters, req.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "query": req.query, "mode": req.mode, "data_version": state.catalog.data_version, "eligible_count": eligible,
        "results": [{"course": card(state.catalog.courses[h.pos]), "retrieval": retrieval(h)} for h in hits],
        "timing_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(req: FeedbackRequest) -> dict[str, Any]:
    ready()
    if state.catalog.get(req.course_id) is None:
        raise HTTPException(status_code=422, detail=f"Unknown course_id '{req.course_id}'.")
    feedback_id, stored_at = state.feedback.add(
        course_id=req.course_id, label=req.label, comment=req.comment, request_id=req.request_id, goal=req.goal,
        goal_track=req.goal_track, known_skills=req.known_skills, simulated_skills=req.simulated_skills,
        is_simulation=req.is_simulation, data_version=state.catalog.data_version,
    )
    return {"feedback_id": feedback_id, "stored_at": stored_at}


@app.get("/evaluation")
def evaluation() -> dict[str, Any]:
    """Read the latest saved report; never triggers model work."""
    if not config.EVAL_REPORT_JSON.exists():
        return {"available": False, "message": "Not evaluated yet. Run scripts/evaluate.py to produce a report."}
    report = json.loads(config.EVAL_REPORT_JSON.read_text(encoding="utf-8"))
    return {"available": True, **report}
