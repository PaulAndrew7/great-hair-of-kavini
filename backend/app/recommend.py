"""The single /recommend pipeline: profile -> retrieval -> gaps -> path -> personalised ranking -> advice.

What-If requests run through exactly this code with simulated skills added to the effective set.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import numpy as np

from . import config
from .advisor import explain
from .catalog import Catalog
from .learning_path import PathContext, build_path
from .live_eval import LiveEvaluator
from .prerequisites import PrereqModel
from .schemas import RecommendRequest
from .search import Filters, Hit, SearchEngine, tokenize
from .skills import SkillModel, TrackMatch
from .track_designer import TRACK_ID as AI_TRACK_ID, DraftTrack, LLMError, TrackDesigner

SKILL_QUERY = {
    "Cloud Platforms": "AWS, Microsoft Azure or Google Cloud platform",
    "BI Dashboards": "Tableau or Power BI dashboards",
    "Containers": "Docker containers",
    "Spreadsheets": "Excel spreadsheets",
    "Networking": "computer networking fundamentals",
}
_PREREQ_ORDER = {"met": 0, "unknown": 1, "unmet": 2}


def card(course: dict[str, Any]) -> dict[str, Any]:
    suspect = course["description_quality"] == "Suspect"
    return {
        "course_id": course["course_id"],
        "title": course["title"],
        "organization": course["organization"],
        "difficulty": course["difficulty"],
        "rating": course["rating"],
        "num_reviews": course["num_reviews"],
        "enrolled": course["enrolled"],
        "duration_text": course["duration_text"],
        "structure_text": course["structure_text"],
        "course_type": course["course_type"],
        "course_url": course["course_url"],
        "summary": None if suspect else course["summary"],
        "description_quality": course["description_quality"],
        "quality_notes": course["quality_notes"],
        "skills": course["skills"][:12],
        "track_skills": course["track_skills"],
    }


def retrieval(hit: Hit) -> dict[str, Any]:
    return {
        "fused_rank": hit.fused_rank,
        "bm25_rank": hit.bm25_rank,
        "semantic_rank": hit.semantic_rank,
        "semantic_similarity": None if hit.semantic_similarity is None else round(hit.semantic_similarity, 3),
        "matched_terms": hit.matched_terms,
    }


class Recommender:
    def __init__(self, catalog: Catalog, engine: SearchEngine, skills: SkillModel, prereqs: PrereqModel):
        self.catalog = catalog
        self.engine = engine
        self.skills = skills
        self.prereqs = prereqs
        self.designer: TrackDesigner | None = None  # set by main.startup when an LLM key is configured
        self.evaluator = LiveEvaluator(engine, skills)
        vectors = None
        if engine.embedder is not None:
            names = list(skills.skills)
            encoded = engine.embedder.encode([SKILL_QUERY.get(n, n) + " course" for n in names])
            vectors = dict(zip(names, encoded))
        self._annotate_strength(vectors)
        self.path_ctx = PathContext(catalog, skills, prereqs, vectors)

    def _annotate_strength(self, vectors: dict[str, np.ndarray] | None) -> None:
        """Mark each tagged track skill as the course's primary subject or merely listed.

        Catalog tags include tools a course only uses (a GLM course tagged Calculus). Title evidence
        is always primary; tag evidence is primary when the course embedding is close to the skill.
        Without the model (keyword-only mode) every tag counts as primary.
        """
        for pos, course in enumerate(self.catalog.courses):
            for ev in course["track_skills"]:
                if vectors is None or ev["source"] == "course title":
                    ev["strength"] = "primary"
                else:
                    sim = float(self.catalog.embeddings[pos] @ vectors[ev["skill"]])
                    ev["strength"] = "primary" if sim >= config.PRIMARY_SKILL_SIMILARITY else "listed"

    def _track(self, req: RecommendRequest, match: TrackMatch) -> tuple[PathContext, DraftTrack | None, str | None]:
        """Auto (no track chosen) asks the designer for a drafted track, adapted from a detected curated one.

        A chosen track, a missing key or a gateway failure keeps the curated rules.
        """
        if req.goal_track or self.designer is None:
            return self.path_ctx, None, None
        base = match.track_id if match.status == "detected" else None
        try:
            draft = self.designer.design(req.goal, base)
        except LLMError as exc:
            return self.path_ctx, None, str(exc)
        return draft.ctx, draft, None

    def _profile(self, req: RecommendRequest, parse: Any, match: TrackMatch, skills: SkillModel,
                 draft: DraftTrack | None) -> dict[str, Any]:
        canon = skills.canonical
        excluded = {canon(s) for s in req.excluded_skills}
        explicit = [canon(s) for s in req.known_skills]
        inferred = [s for s in parse.known if s not in excluded and s not in explicit]
        confirmed = list(dict.fromkeys(explicit + [s for s in inferred if s not in explicit]))
        simulated = [s for s in dict.fromkeys(canon(s) for s in req.simulated_skills) if s not in confirmed]
        notes = []
        if parse.negated:
            notes.append("Not counted as known: " + ", ".join(parse.negated) + " (your goal says you don't know it).")
        if parse.beginner:
            notes.append("You mentioned starting from the basics, so beginner-level courses are preferred in the path.")
        track = skills.tracks.get(match.track_id) if match.track_id else None
        ai_track = None
        if draft:
            ai_track = {
                "model": config.LLM_MODEL_LABEL,
                "base_track": draft.base,
                "base_label": self.skills.tracks[draft.base]["label"] if draft.base else None,
                "new_skills": draft.new_skills,
                "left_out": draft.left_out,
                "unteachable": draft.unteachable,
                "notes": draft.notes,
            }
        profile = {
            "goal": req.goal,
            "search_text": parse.target_text,
            "track_id": match.track_id,
            "track_label": track["label"] if track else None,
            "track_status": match.status,
            "track_candidates": match.candidates,
            "ai_track": ai_track,
            "confirmed_skills": confirmed,
            "inferred_skills": inferred,
            "negated_skills": parse.negated,
            "excluded_skills": sorted(excluded),
            "simulated_skills": simulated,
            "effective_skills": list(dict.fromkeys(confirmed + simulated)),
            "beginner": parse.beginner,
            "notes": notes,
        }
        return profile

    def recommend(self, req: RecommendRequest) -> dict[str, Any]:
        started = time.perf_counter()
        parse = self.skills.parse_goal(req.goal)
        match = self.skills.detect_track(parse, req.goal, req.goal_track)
        ctx, draft, ai_error = self._track(req, match)
        sk = ctx.skills
        if draft:
            parse = sk.parse_goal(req.goal)  # the drafted track's new skill names now count as mentions
            match = TrackMatch(AI_TRACK_ID, "generated", [], match.scores)
        profile = self._profile(req, parse, match, sk, draft)
        confirmed = set(profile["confirmed_skills"])
        simulated = set(profile["simulated_skills"])
        effective = confirmed | simulated
        filters = Filters(req.filters.difficulty, req.filters.organization, req.filters.min_rating)
        eligible = self.engine.eligible(filters)
        eligible_count = int(eligible.sum())
        warnings: list[dict[str, str]] = []
        if self.engine.mode == "keyword_only":
            warnings.append({"code": "keyword_only", "message": "Semantic search is unavailable; results use keyword matching only."})
        if ai_error:
            warnings.append({"code": "ai_track_unavailable",
                             "message": f"The AI track designer is unavailable ({ai_error}); using the curated tracks."})

        track_id = profile["track_id"]
        search_text = profile["search_text"]
        if req.goal_track and not parse.mentioned:
            # The student picked a track the goal text never names; let retrieval see it too.
            search_text = f"{search_text} {sk.tracks[track_id]['query_hint']}"
        query_vec = self.engine.encode_query(search_text)
        hits = self.engine.hybrid(search_text, filters, query_vec=query_vec,
                                  mode="hybrid" if self.engine.embedder else "bm25")

        # Skill gap and path -------------------------------------------------------
        gap = None
        gap_out: dict[str, Any]
        path_out: dict[str, Any]
        path_by_pos: dict[int, int] = {}
        if track_id:
            gap = sk.gap(track_id, confirmed, simulated)
            path = build_path(ctx, track_id, effective, eligible, query_vec, parse.beginner,
                              bool(filters.active()))
            for step in path["steps"]:
                path_by_pos[step["pos"]] = step["step"]
            step_of_skill = {s: step["step"] for step in path["steps"] for s in step["new_skills"]}
            targets = gap["targets"]
            projected = set(path["projected_skills"])
            gap_out = {
                "available": True,
                "track_id": track_id,
                "tiles": [
                    {
                        "skill": s,
                        "abbr": sk.skills[s]["abbr"],
                        "period": sk.period[s],
                        "group": "target" if s in targets else "supporting",
                        "state": gap["state"][s],
                        "course_count": len(ctx.courses_for(s)),
                        "requires": sk.deps.get(s, []),
                        "reason": sk.dep_reason.get(s),
                        "origin": sk.origin.get(s, "curated"),
                        "path_step": step_of_skill.get(s),
                    }
                    for s in gap["required"]
                ],
                "target_skills": targets,
                "supporting_skills": gap["supporting"],
                "known_in_track": gap["known_in_track"],
                "other_known": gap["other_known"],
                "missing_targets": gap["missing_targets"],
                "missing_supporting": gap["missing_supporting"],
                "coverage": {
                    "covered_now": sum(1 for s in targets if s in effective),
                    "projected": sum(1 for s in targets if s in projected),
                    "total": len(targets),
                },
            }
            path_out = {
                "available": True,
                "steps": [
                    {
                        "step": st["step"],
                        "course": card(ctx.course(st["pos"])),
                        "new_skills": st["new_skills"],
                        "new_skill_evidence": st["new_skill_evidence"],
                        "prerequisites": st["prerequisites"],
                        "also_lists": st["also_lists"],
                        "notes": st["notes"],
                        "match": st["match"],
                    }
                    for st in path["steps"]
                ],
                "projected_skills": path["projected_skills"],
                "unresolved": path["unresolved"],
                "complete": path["complete"],
            }
            if not gap["missing"]:
                path_out["reason"] = "You already have every skill this track models; no path is needed."
            if draft and draft.left_out:
                warnings.append({"code": "ai_skill_left_out",
                                 "message": "The AI-drafted track also named " + ", ".join(draft.left_out)
                                 + (", but no catalog course mainly teaches it, so it was left out." if len(draft.left_out) == 1
                                    else ", but no catalog course mainly teaches them, so they were left out.")})
            elif path["unresolved"]:
                warnings.append({"code": "path_incomplete",
                                 "message": "The learning path leaves " + ", ".join(u["skill"] for u in path["unresolved"]) + " uncovered."})
        else:
            if profile["track_status"] == "ambiguous":
                labels = [sk.tracks[t]["label"] for t in profile["track_candidates"]]
                reason = "Your goal fits more than one track (" + " or ".join(labels) + "). Choose one to see skill gaps and a path."
                warnings.append({"code": "ambiguous_track", "message": reason})
            else:
                reason = ("Skill gaps and learning paths cover machine learning, data analytics and cloud computing. "
                          "Search results below still match your goal.")
                warnings.append({"code": "unsupported_track", "message": "No structured path for this goal yet; showing search results only."})
            gap_out = {"available": False, "reason": reason}
            path_out = {"available": False, "reason": reason}

        # Personalise the top relevant candidates ----------------------------------
        candidates = hits[: config.PERSONALIZE_DEPTH]
        missing_targets = set(gap["missing_targets"]) if gap else set()
        ranked = []
        for hit in candidates:
            course = ctx.course(hit.pos)
            prereq = ctx.prereqs.status(course, effective)
            taught = set(ctx.prereqs.primary(course))
            fills = (gap and [s for s in gap["missing"] if s in taught]) or []
            key = (
                _PREREQ_ORDER[prereq["status"]],
                -len(taught & missing_targets),
                hit.fused_rank,
                -(course["rating"] or 0.0),
                course["course_id"],
            )
            ranked.append((key, hit, course, prereq, fills))
        ranked.sort(key=lambda r: r[0])

        q_tokens = list(dict.fromkeys(tokenize(search_text)))
        labelled = self.evaluator.labelled_query(req.goal)
        ground = self.evaluator.judgments.get(labelled["id"]) if labelled else None
        courses = []
        for rank, (_, hit, course, prereq, fills) in enumerate(ranked[: req.top_k], start=1):
            step = path_by_pos.get(hit.pos)
            courses.append({
                **card(course),
                "rank": rank,
                "retrieval": retrieval(hit) | self.evaluator.course_evidence(hit, q_tokens, query_vec, ground),
                "prerequisites": prereq,
                "fills_gaps": fills,
                "path_step": step,
                "advisor": explain(course, hit, prereq, gap, effective, simulated, step, parse.beginner),
            })

        if not hits:
            if filters.active() and self.engine.hybrid(search_text, Filters(), query_vec=query_vec,
                                                       mode="hybrid" if self.engine.embedder else "bm25"):
                warnings.append({"code": "filters_excluded", "message": "No course matches with these filters. Loosen a filter to see results."})
            else:
                warnings.append({"code": "no_matches", "message": "No course in the catalog matches this goal closely enough."})
        elif len(courses) < req.top_k:
            warnings.append({"code": "few_matches", "message": f"Only {len(courses)} course(s) matched closely enough; the rest were not padded in."})

        return {
            "request_id": uuid.uuid4().hex[:16],
            "data_version": self.catalog.data_version,
            "rules_version": sk.version,
            "mode": self.engine.mode,
            "is_simulation": bool(simulated),
            "filters_applied": filters.active(),
            "eligible_count": eligible_count,
            "profile": profile,
            "courses": courses,
            "skill_gap": gap_out,
            "learning_path": path_out,
            "evaluation": self.evaluator.evaluate(
                req=req, profile=profile, match=match, hits=hits, shown=courses, search_text=search_text,
                gap_out=gap_out, path_out=path_out, effective=effective, top_k=req.top_k, skills=sk),
            "warnings": warnings,
            "timing_ms": round((time.perf_counter() - started) * 1000, 1),
        }
