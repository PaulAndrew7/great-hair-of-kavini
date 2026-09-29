"""Per-request evaluation: every /recommend answer carries its own accuracy and confidence evidence.

Three kinds of numbers, kept apart so none is passed off as another:
  estimated  calibrated confidence from retrieval signals (app/confidence.py), available for any query
  measured   labelled ground truth, only when the goal is one of the frozen evaluation queries or profiles
  checked    rule checks that need no labels (path prerequisites, duplicates, coverage, track-cue margin)
The offline report's held-out numbers are attached as the system-level reference.
"""
from __future__ import annotations

import json
import re
from typing import Any

import numpy as np

from . import config
from .confidence import Calibration, band, features
from .search import Hit, SearchEngine, tokenize
from .skills import SkillModel, TrackMatch

AGREEMENT_DEPTH = 10


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _read(path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (OSError, ValueError):
        return None


class LiveEvaluator:
    def __init__(self, engine: SearchEngine, skills: SkillModel) -> None:
        self.engine = engine
        self.skills = skills
        self.calibration = Calibration.load(config.CALIBRATION_JSON)
        queries = _read(config.EVAL_QUERIES_JSON) or {}
        judgments = (_read(config.EVAL_JUDGMENTS_JSON) or {}).get("judgments", {})
        self.queries = {normalize(q["text"]): q for q in queries.get("queries", [])}
        self.judgments: dict[str, dict[str, Any]] = judgments
        self.profiles = (_read(config.EVAL_PROFILES_JSON) or {}).get("profiles", [])
        self.report = _read(config.EVAL_REPORT_JSON)

    # Per-course signals --------------------------------------------------------------------------
    def signals(self, hit: Hit, query_vec: np.ndarray | None) -> dict[str, float]:
        """Model inputs for one fused hit; scripts/evaluate.py calibrates on exactly these."""
        sim = None if query_vec is None else float(self.engine.catalog.embeddings[hit.pos] @ query_vec)
        return features(sim, hit.semantic_rank, hit.bm25_rank is not None and hit.semantic_rank is not None)

    def course_evidence(self, hit: Hit, q_tokens: list[str], query_vec: np.ndarray | None,
                        ground: dict[str, Any] | None) -> dict[str, Any]:
        row = self.signals(hit, query_vec)
        p = self.calibration.probability(self.engine.mode, row) if self.calibration else None
        doc = self.engine.doc_token_sets[hit.pos]
        matched = [t for t in q_tokens if t in doc]
        label = ground.get(hit.course_id) if ground else None
        return {
            "confidence": None if p is None else round(p, 3),
            "confidence_band": band(p),
            "cosine": None if query_vec is None else round(row["sim"], 3),
            "keyword_coverage": round(len(matched) / len(q_tokens), 3) if q_tokens else 0.0,
            "query_terms": len(q_tokens),
            "matched_query_terms": matched,
            "channels": (hit.bm25_rank is not None) + (hit.semantic_rank is not None),
            "judged_relevant": None if label is None else bool(label["relevant"]),
            "judgment_reason": None if label is None else label.get("reason"),
        }

    def labelled_query(self, goal: str) -> dict[str, Any] | None:
        q = self.queries.get(normalize(goal))
        return q if q and q["id"] in self.judgments else None

    # Per-query evaluation ------------------------------------------------------------------------
    def evaluate(self, *, req, profile: dict[str, Any], match: TrackMatch, hits: list[Hit], shown: list[dict[str, Any]],
                 search_text: str, gap_out: dict[str, Any], path_out: dict[str, Any], effective: set[str],
                 top_k: int, skills: SkillModel | None = None) -> dict[str, Any]:
        skills = skills or self.skills  # an AI-drafted track brings its own skill graph
        mode = self.engine.mode
        notes: list[str] = []
        q_tokens = list(dict.fromkeys(tokenize(search_text)))
        confs = [c["retrieval"]["confidence"] for c in shown]
        have_conf = bool(shown) and all(v is not None for v in confs)

        # Retrieval: estimated
        agreement = None
        if mode == "hybrid":
            kw_top = {h.course_id for h in hits if h.bm25_rank is not None and h.bm25_rank <= AGREEMENT_DEPTH}
            sem_top = {h.course_id for h in hits if h.semantic_rank is not None and h.semantic_rank <= AGREEMENT_DEPTH}
            if kw_top and sem_top:
                agreement = round(len(kw_top & sem_top) / min(AGREEMENT_DEPTH, len(kw_top), len(sem_top)), 3)
            elif kw_top or sem_top:
                agreement = 0.0
        covered_terms = set().union(*(set(c["retrieval"]["matched_query_terms"]) for c in shown)) if shown else set()
        expected_relevant = round(sum(confs), 2) if have_conf else None
        # Every labelled query belongs to a supported track; elsewhere the model is applied outside what it saw.
        ai = profile.get("ai_track")
        extrapolated = profile["track_status"] == "unsupported" or bool(ai and not ai["base_track"])
        retrieval = {
            "extrapolated": extrapolated,
            "shown": len(shown),
            "k": top_k,
            "expected_relevant": expected_relevant,
            "expected_precision": None if expected_relevant is None else round(expected_relevant / top_k, 3),
            "top_confidence": round(max(confs), 3) if have_conf else None,
            "min_confidence": round(min(confs), 3) if have_conf else None,
            "channel_agreement": agreement,
            "agreement_depth": AGREEMENT_DEPTH,
            "query_terms": q_tokens,
            "unmatched_terms": [t for t in q_tokens if t not in covered_terms],
        }
        if extrapolated and have_conf:
            notes.append("Confidence was calibrated on machine learning, data analytics and cloud queries only; for "
                         "this subject it is extrapolated and likely too high.")
        if not self.calibration:
            notes.append("No calibration file: run scripts/evaluate.py to enable confidence estimates.")

        # Retrieval: measured, when this is a labelled evaluation query
        ground_truth = None
        q = self.labelled_query(req.goal)
        if q:
            labels = [c["retrieval"]["judged_relevant"] for c in shown]
            judged = [v for v in labels if v is not None]
            rel = sum(1 for v in judged if v)
            ground_truth = {
                "query_id": q["id"], "split": q["split"], "judged": len(judged), "relevant": rel, "shown": len(shown),
                "precision_at_k": round(rel / top_k, 3),
                "rr_at_k": next((round(1 / (i + 1), 3) for i, v in enumerate(labels) if v), 0.0),
                "note": ("All shown courses have a label." if len(judged) == len(shown) else
                         f"{len(shown) - len(judged)} shown course(s) were never labelled and count as misses, "
                         "so this is a lower bound."),
            }
            if have_conf:
                notes.append(f"Labelled {q['split']} query: estimated {expected_relevant:.1f} relevant of {top_k}, "
                             f"labelled {rel} of {top_k}.")
        else:
            notes.append("This exact query has no human labels, so retrieval accuracy here is an estimate, not a measurement.")

        # Track detection: checked
        track = self._track(profile, match)

        # Skill gap: measured, when this is a frozen evaluation profile with the same chip edits
        # A what-if gap treats simulated skills as known, so the profile's labelled gap does not apply to it.
        skill_gap = (self._gap(req, gap_out, profile["confirmed_skills"])
                     if gap_out.get("available") and not profile["simulated_skills"] else None)

        # Path: checked
        path = self._path(path_out, gap_out, effective, skills) if path_out.get("available") else None

        return {
            "retrieval": retrieval,
            "calibration": self._calibration_summary(),
            "ground_truth": ground_truth,
            "track": track,
            "skill_gap": skill_gap,
            "path": path,
            "reference": self._reference(),
            "notes": notes,
        }

    def _track(self, profile: dict[str, Any], match: TrackMatch) -> dict[str, Any]:
        labels = {tid: t["label"] for tid, t in self.skills.tracks.items()}
        scores = dict(match.scores)
        ordered = sorted(scores.values(), reverse=True)
        margin = (ordered[0] - ordered[1]) if len(ordered) > 1 else (ordered[0] if ordered else 0)
        status = profile["track_status"]
        ai = profile.get("ai_track")
        if status == "generated" and ai:
            base = f"adapted from the curated {ai['base_label'].lower()} track" if ai["base_label"] else "a new track"
            text = f"Drafted by {ai['model']} for this goal, {base}. Its skills and order are unreviewed suggestions"
            if ai["unteachable"]:
                text += f"; no catalog course mainly teaches {len(ai['unteachable'])} of its skills."
            elif ai["left_out"]:
                text += f"; {len(ai['left_out'])} proposed skill(s) left out because no catalog course mainly teaches them."
            else:
                text += "; every skill in it has catalog courses."
            return {"status": status, "confidence": "drafted", "scores": {labels[t]: n for t, n in scores.items()},
                    "margin": margin, "explanation": text}
        if status == "selected":
            confidence, text = "certain", "You chose this track, so nothing was guessed."
        elif status == "detected":
            best = ordered[0]
            # Cues for one track only: unambiguous. Cues for several with a winner: medium.
            confidence = "high" if best == sum(ordered) or margin >= 2 else "medium"
            others = [f"{labels[t]} {n}" for t, n in scores.items() if t != profile["track_id"] and n]
            text = (f"{best} {labels[profile['track_id']].lower()} cue(s) in your goal"
                    + (f"; also {', '.join(others)}." if others else "; none for other tracks."))
        elif status == "ambiguous":
            confidence = "low"
            text = "Tied between " + " and ".join(labels[t] for t in match.candidates) + "; choose one."
        else:
            confidence, text = "none", "No cue for any supported track."
        return {"status": status, "confidence": confidence, "scores": {labels[t]: n for t, n in scores.items()},
                "margin": margin, "explanation": text}

    def _gap(self, req, gap_out: dict[str, Any], confirmed: list[str]) -> dict[str, Any] | None:
        """Score against a frozen profile when the student ends up with the same skills that profile describes.

        Compared on the resulting confirmed set, not the raw request, so chips carried over from an earlier goal
        that the goal text also names still count as the same profile.
        """
        canon = self.skills.canonical
        for p in self.profiles:
            if normalize(p["goal"]) != normalize(req.goal):
                continue
            excluded = {canon(s) for s in p.get("excluded_skills", [])}
            expected_confirmed = ({canon(s) for s in p.get("known_skills", [])}
                                  | {s for s in self.skills.parse_goal(p["goal"]).known if s not in excluded})
            if expected_confirmed == set(confirmed):
                predicted = set(gap_out["missing_targets"]) | set(gap_out["missing_supporting"])
                expected = set(p["expected_missing"])
                tp = len(predicted & expected)
                precision = tp / len(predicted) if predicted else 1.0
                recall = tp / len(expected) if expected else 1.0
                f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
                return {"profile_id": p["id"], "precision": round(precision, 3), "recall": round(recall, 3),
                        "f1": round(f1, 3), "exact": predicted == expected,
                        "false_positives": sorted(predicted - expected), "false_negatives": sorted(expected - predicted)}
        return None

    def _path(self, path_out: dict[str, Any], gap_out: dict[str, Any], effective: set[str],
              skills: SkillModel) -> dict[str, Any]:
        steps = path_out["steps"]
        covered = set(effective)
        violations: list[str] = []
        unverified = 0
        for step in steps:
            for need in step["prerequisites"]["required"]:
                if need not in covered:
                    violations.append(f"Step {step['step']} needs {need}")
            for skill in step["new_skills"]:
                for need in skills.deps.get(skill, []):
                    if need not in covered:
                        violations.append(f"Step {step['step']} teaches {skill} before {need}")
            unverified += step["prerequisites"]["status"] == "unknown"
            covered |= set(step["new_skills"])
        ids = [s["course"]["course_id"] for s in steps]
        cov = gap_out.get("coverage")
        match_scores = [s["match"]["skill_similarity"] for s in steps if s.get("match", {}).get("skill_similarity") is not None]
        return {
            "steps": len(steps),
            "target_coverage_now": None if not cov else round(cov["covered_now"] / cov["total"], 3),
            "target_coverage_projected": None if not cov else round(cov["projected"] / cov["total"], 3),
            "unresolved": len(path_out["unresolved"]),
            "duplicates": len(ids) - len(set(ids)),
            "prerequisite_violations": len(violations),
            "violations": violations,
            "unverified_steps": unverified,
            "mean_skill_similarity": round(sum(match_scores) / len(match_scores), 3) if match_scores else None,
        }

    def _calibration_summary(self) -> dict[str, Any] | None:
        if not self.calibration:
            return None
        m = self.calibration.model(self.engine.mode)
        if m is None:
            return None
        d = self.calibration.data
        return {"labels": d["labels"], "queries": d["queries"], "base_rate": d["base_rate"], "features": m["features"],
                "method": d["method"], **{k: m["cross_validation"][k] for k in
                                          ("brier", "baseline_brier", "log_loss", "accuracy", "auc", "reliability")}}

    def _reference(self) -> dict[str, Any] | None:
        r = self.report
        if not r:
            return None
        mode = "hybrid" if self.engine.mode == "hybrid" else "bm25"
        test = next((b for b in r.get("retrieval", []) if b["split"] == "test"), None)
        row = next((x for x in (test or {}).get("rows", []) if x["mode"] == mode), None)
        return {
            "created": r.get("created"),
            "mode": mode,
            "precision_at_5": row and row["precision_at_5"],
            "mrr_at_5": row and row["mrr_at_5"],
            "queries": row and row["queries"],
            "gap_f1": r.get("skill_gap", {}).get("f1"),
            "gap_profiles": r.get("skill_gap", {}).get("profiles"),
            "path_target_coverage": r.get("paths", {}).get("target_coverage"),
            "path_prerequisite_violations": r.get("paths", {}).get("prerequisite_violations"),
        }
