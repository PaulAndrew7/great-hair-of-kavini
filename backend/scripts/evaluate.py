"""Evaluation runner: measures the same engine and /recommend pipeline that serve Discover.

Usage (from backend/):
  .venv/Scripts/python scripts/evaluate.py pool   # write data/evaluation/pool.json: unjudged top-5 candidates, blind
  .venv/Scripts/python scripts/evaluate.py        # score everything and write data/evaluation/report.json

Scoring refuses to run while any top-5 result lacks a judgment, so no metric counts an unjudged course.
Feedback written during the run goes to a temporary database, never the real one.
"""
from __future__ import annotations

import json
import os
import platform
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402

QUERIES_JSON = config.EVAL_DIR / "queries.json"
PROFILES_JSON = config.EVAL_DIR / "profiles.json"
JUDGMENTS_JSON = config.EVAL_DIR / "judgments.json"
POOL_JSON = config.EVAL_DIR / "pool.json"
MODES = ("bm25", "semantic", "hybrid")
K = 5
LATENCY_REQUESTS = 30
WARMUP_REQUESTS = 3


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def start_service():
    """Start the real app in-process with a throwaway feedback DB. Returns (client, state, startup seconds)."""
    config.FEEDBACK_DB = Path(tempfile.mkdtemp()) / "feedback.sqlite3"
    from fastapi.testclient import TestClient

    from app import main

    client = TestClient(main.app)
    client.__enter__()
    if main.state.recommender is None:
        sys.exit(f"Service unavailable: {main.state.error}")
    return client, main.state


def top_k(state, text: str, mode: str) -> list[str]:
    from app.search import Filters

    search_text = state.skills.parse_goal(text).target_text  # exactly what Discover searches for
    hits, _ = state.engine.search(search_text, mode, Filters(), K)
    return [h.course_id for h in hits]


def runs(state, queries: list[dict]) -> dict[str, dict[str, list[str]]]:
    return {q["id"]: {m: top_k(state, q["text"], m) for m in MODES} for q in queries}


# Pool ---------------------------------------------------------------------------------------------


def write_pool() -> None:
    queries = load(QUERIES_JSON)
    judged = load(JUDGMENTS_JSON)["judgments"] if JUDGMENTS_JSON.exists() else {}
    _, state = start_service()
    from app.recommend import card

    pool, total = [], 0
    for q in queries["queries"]:
        ranked = runs(state, [q])[q["id"]]
        ids = sorted({cid for m in MODES for cid in ranked[m]} - set(judged.get(q["id"], {})))  # sorted: method order hidden
        total += len(ids)
        if not ids:
            continue
        candidates = []
        for cid in ids:
            c = card(state.catalog.get(cid))
            candidates.append({k: c[k] for k in ("course_id", "title", "organization", "difficulty", "course_type",
                                                 "description_quality", "summary")} | {"skills": c["skills"][:8]})
        pool.append({"query_id": q["id"], "query": q["text"], "candidates": candidates})
    POOL_JSON.write_text(json.dumps({"relevance_rule": queries["relevance_rule"], "pool": pool}, indent=1, ensure_ascii=False),
                         encoding="utf-8")
    print(f"{total} unjudged candidates across {len(pool)} queries -> {POOL_JSON}")


# Scoring --------------------------------------------------------------------------------------------


def retrieval_metrics(queries: list[dict], ranked: dict, judgments: dict) -> list[dict]:
    missing = [(q["id"], cid) for q in queries for m in MODES for cid in ranked[q["id"]][m]
               if cid not in judgments.get(q["id"], {})]
    if missing:
        sys.exit(f"{len(missing)} top-{K} results are unjudged (e.g. {missing[:3]}). Run 'evaluate.py pool' and judge them.")
    blocks = []
    for split in ("dev", "test"):
        subset = [q for q in queries if q["split"] == split]
        rows, per_query = [], []
        for mode in MODES:
            p_values, rr_values = [], []
            for q in subset:
                ids = ranked[q["id"]][mode]
                rel = [judgments[q["id"]][cid]["relevant"] for cid in ids]
                p = sum(rel) / K  # unfilled positions count as misses
                rr = next((1 / (i + 1) for i, r in enumerate(rel) if r), 0.0)
                p_values.append(p)
                rr_values.append(rr)
                per_query.append({"query_id": q["id"], "query": q["text"], "mode": mode, "results": ids,
                                  "relevant": rel, "precision_at_5": p, "rr_at_5": rr})
            rows.append({"mode": mode, "precision_at_5": round(statistics.mean(p_values), 3),
                         "mrr_at_5": round(statistics.mean(rr_values), 3), "queries": len(subset)})
        blocks.append({"split": split, "rows": rows, "per_query": per_query})
    return blocks


def gap_and_path_metrics(client, profiles: list[dict], deps: dict[str, list[str]]) -> tuple[dict, dict]:
    tp = n_pred = n_exp = exact = 0
    cov, unresolved, dups, violations, unverified = [], 0, 0, 0, 0
    per_profile, notes = [], []
    for p in profiles:
        body = {"goal": p["goal"], "known_skills": p.get("known_skills", []), "excluded_skills": p.get("excluded_skills", [])}
        r = client.post("/recommend", json=body).json()
        gap, path = r["skill_gap"], r["learning_path"]
        predicted = set(gap.get("missing_targets", []) + gap.get("missing_supporting", [])) if gap["available"] else set()
        expected = set(p["expected_missing"])
        hit = predicted & expected
        tp, n_pred, n_exp = tp + len(hit), n_pred + len(predicted), n_exp + len(expected)
        exact += predicted == expected

        covered = set(r["profile"]["effective_skills"])
        ids = [s["course"]["course_id"] for s in path.get("steps", [])]
        profile_violations = []
        for step in path.get("steps", []):
            for need in step["prerequisites"]["required"]:
                if need not in covered:
                    profile_violations.append(f"step {step['step']} needs {need} ({step['prerequisites']['source']})")
            for skill in step["new_skills"]:
                for need in deps.get(skill, []):
                    if need not in covered:
                        profile_violations.append(f"step {step['step']} teaches {skill} before {need}")
            unverified += step["prerequisites"]["status"] == "unknown"
            covered |= set(step["new_skills"])
        if gap["available"] and gap["coverage"]:
            cov.append(gap["coverage"]["projected"] / gap["coverage"]["total"])
        unresolved += len(path.get("unresolved", []))
        dups += len(ids) - len(set(ids))
        violations += len(profile_violations)
        per_profile.append({
            "profile_id": p["id"], "goal": p["goal"], "expected_track": p["track"], "detected_track": r["profile"]["track_id"],
            "confirmed": r["profile"]["confirmed_skills"], "expected_missing": sorted(expected), "predicted_missing": sorted(predicted),
            "false_positives": sorted(predicted - expected), "false_negatives": sorted(expected - predicted),
            "path": [f"{s['step']}. {s['course']['title']} -> {', '.join(s['new_skills'])}" for s in path.get("steps", [])],
            "unresolved": [f"{u['skill']}: {u['reason']}" for u in path.get("unresolved", [])],
            "violations": profile_violations,
        })
        if r["profile"]["track_id"] != p["track"]:
            notes.append(f"{p['id']}: track detected as {r['profile']['track_id'] or r['profile']['track_status']}, expected {p['track']}.")

    precision = tp / n_pred if n_pred else 1.0
    recall = tp / n_exp if n_exp else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    skill_gap = {
        "profiles": len(profiles), "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        "exact_matches": exact,
        "convention": "Micro-averaged over all nine profiles (true positives, predictions and expected skills summed first). "
                      "An empty predicted or expected set scores 1.0 when both are empty; exact-set matches are counted separately.",
        "per_profile": per_profile,
    }
    notes.append("Every path step has modelled prerequisites." if not unverified else
                 f"{unverified} path step(s) use a course whose prerequisites are not verified; the UI labels them.")
    notes.append("Violations check each step against the student's skills plus earlier steps, for both the course's modelled "
                 "prerequisites and the curated skill order. Unknown official prerequisites are not checkable.")
    paths = {"profiles": len(profiles), "target_coverage": round(statistics.mean(cov), 3) if cov else 0.0,
             "unresolved_gaps": unresolved, "duplicate_courses": dups, "prerequisite_violations": violations,
             "unverified_steps": unverified, "notes": notes}
    return skill_gap, paths


def edge_cases(client, cases: list[dict]) -> list[dict]:
    out = []
    for case in cases:
        r = client.post("/recommend", json=case["request"])
        body = r.json()
        codes = [w["code"] for w in body.get("warnings", [])]
        cid = case["id"]
        if cid == "empty":
            passed = r.status_code == 422 and bool(body.get("problems"))
            observed = f"HTTP {r.status_code}: " + "; ".join(p["message"] for p in body.get("problems", []))
        elif cid == "unrelated":
            passed = (r.status_code == 200 and not body["skill_gap"]["available"] and "unsupported_track" in codes
                      and not body["learning_path"]["steps"])
            observed = f"No chart or path; warnings {codes}; {len(body['courses'])} search result(s) shown."
        elif cid == "no_match_filter":
            passed = (r.status_code == 200 and not body["courses"] and "filters_excluded" in codes
                      and not body["learning_path"]["steps"])
            observed = (f"{body['eligible_count']} eligible courses, {len(body['courses'])} shown, "
                        f"{len(body['learning_path']['steps'])} path steps; warnings {codes}.")
        elif cid == "negated":
            prof, gap = body["profile"], body["skill_gap"]
            missing = gap.get("missing_targets", []) + gap.get("missing_supporting", [])
            passed = "SQL" in prof["confirmed_skills"] and "Python" not in prof["confirmed_skills"] and "Python" in missing
            observed = f"Confirmed {prof['confirmed_skills']}; negated {prof['negated_skills']}; Python missing: {'Python' in missing}."
        elif cid == "ambiguous":
            prof = body["profile"]
            passed = prof["track_status"] == "ambiguous" and not body["learning_path"]["available"]
            observed = f"Track status '{prof['track_status']}', candidates {prof['track_candidates']}; path shown: {body['learning_path']['available']}."
        else:
            raise ValueError(f"no check defined for edge case {cid}")
        out.append({"name": case["name"], "expected": case["expected"], "observed": observed, "passed": passed})
    return out


def findings(retrieval: list[dict], skill_gap: dict, edges: list[dict]) -> list[str]:
    """Plain statements generated from this run's numbers, so they stay true when the report is regenerated."""
    out = []
    label = {"bm25": "keyword", "semantic": "semantic", "hybrid": "hybrid"}
    def leaders(rows: list[dict], metric: str) -> str:
        top = max(r[metric] for r in rows)
        names = [label[r["mode"]] for r in rows if r[metric] == top]
        return f"{' and '.join(names)} {'tie' if len(names) > 1 else 'leads'} on {metric.replace('_at_5', '@5').replace('precision', 'Precision').replace('mrr', 'MRR')} ({top:.2f})"

    for block in retrieval:
        out.append(f"{block['split'].capitalize()} queries: {leaders(block['rows'], 'precision_at_5')}; "
                   f"{leaders(block['rows'], 'mrr_at_5')}.")
        by_query: dict[str, dict[str, float]] = {}
        for row in block["per_query"]:
            by_query.setdefault(row["query_id"], {})[row["mode"]] = row["precision_at_5"]
        behind = [q for q, v in by_query.items() if round(max(v["bm25"], v["semantic"]) - v["hybrid"], 6) >= 0.4]
        if behind:
            out.append(f"Hybrid trails the best single method by 0.4 or more Precision@5 on {', '.join(behind)} "
                       f"({block['split']}).")
    for p in skill_gap["per_profile"]:
        parts = []
        if p["false_positives"]:
            parts.append(", ".join(p["false_positives"]) + " counted as missing although the student has it")
        if p["false_negatives"]:
            parts.append(", ".join(p["false_negatives"]) + " not counted as missing")
        if parts:
            out.append(f"Skill gap {p['profile_id']} (“{p['goal']}”): " + "; ".join(parts) + ".")
    for e in edges:
        if not e["passed"]:
            out.append(f"Edge case failed: {e['name']}. {e['observed']}")
    return out


def latency(client, goals: list[str]) -> dict:
    for goal in goals[:WARMUP_REQUESTS]:
        client.post("/recommend", json={"goal": goal})
    wall, server = [], []
    for i in range(LATENCY_REQUESTS):
        t0 = time.perf_counter()
        r = client.post("/recommend", json={"goal": goals[i % len(goals)]})
        wall.append((time.perf_counter() - t0) * 1000)
        server.append(r.json()["timing_ms"])
    wall.sort()
    p95 = wall[max(0, int(round(0.95 * len(wall))) - 1)]  # nearest-rank
    return {"requests": len(wall), "median_ms": round(statistics.median(wall), 1), "p95_ms": round(p95, 1),
            "max_ms": round(wall[-1], 1), "server_median_ms": round(statistics.median(server), 1)}


def machine() -> str:
    cpu = platform.processor() or platform.machine()
    return f"{platform.system()} {platform.release()}, {cpu}, {os.cpu_count()} logical CPUs, Python {platform.python_version()}, CPU inference"


def run() -> None:
    queries, profiles = load(QUERIES_JSON), load(PROFILES_JSON)
    if not JUDGMENTS_JSON.exists():
        sys.exit("judgments.json missing: run 'evaluate.py pool' and judge the pool first.")
    judgments = load(JUDGMENTS_JSON)

    t0 = time.perf_counter()
    client, state = start_service()
    cold_start_ms = (time.perf_counter() - t0) * 1000
    catalog_info = client.get("/catalog").json()
    deps = {s["skill"]: s["requires"] for s in catalog_info["track_skills"]}

    ranked = runs(state, queries["queries"])
    retrieval = retrieval_metrics(queries["queries"], ranked, judgments["judgments"])
    skill_gap, paths = gap_and_path_metrics(client, profiles["profiles"], deps)
    edges = edge_cases(client, queries["edge_cases"])
    lat = latency(client, [q["text"] for q in queries["queries"]])
    lat |= {"cold_start_ms": round(cold_start_ms, 1), "machine": machine() + ". Warm requests run in-process through "
            "FastAPI (routing, validation, serialisation) without a network hop; cold start covers catalog load, BM25 "
            "index build and model load after Python imports."}
    client.__exit__(None, None, None)

    manifest = state.catalog.manifest
    report = {
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "conditions": {
            "Catalog version": state.catalog.data_version,
            "Courses": len(state.catalog.courses),
            "Source file": f"{manifest['source']['file']} @ {manifest['source']['revision'][:12]}",
            "Embedding model": f"{config.MODEL_NAME.split('/')[-1]} @ {config.MODEL_REVISION[:12]}",
            "Rules version": state.skills.version,
            "Query set": f"{queries['version']} ({sum(q['split'] == 'dev' for q in queries['queries'])} dev, "
                         f"{sum(q['split'] == 'test' for q in queries['queries'])} test)",
            "Judgments": f"{judgments['version']}, {judgments['judge']}",
            "Retrieval": f"RRF k={config.RRF_K}, depth {config.CHANNEL_DEPTH} per channel, semantic floor {config.SEMANTIC_MIN_SIMILARITY}",
        },
        "retrieval": retrieval,
        "skill_gap": skill_gap,
        "paths": paths,
        "latency": lat,
        "edge_cases": edges,
        "findings": findings(retrieval, skill_gap, edges),
        "limitations": [
            "Relevance labels come from one judge over pooled top-5 results of the three compared methods. They are not "
            "exhaustive catalog labels, so no catalog-wide recall is claimed.",
            f"{len(queries['queries'])} queries is a small sample: one query changes a split's Precision@5 by up to "
            f"{1 / sum(q['split'] == 'test' for q in queries['queries']):.2f}.",
            "Skill-gap expectations follow the project's curated track definitions; they test profile reading and gap "
            "arithmetic, not whether the curriculum itself is right.",
            "Course prerequisites are verified for a handful of courses only; the rest use curated skill guidance or are "
            "labelled not verified.",
            "Latency was measured on one development machine; it will differ on other hardware.",
        ],
    }
    config.EVAL_REPORT_JSON.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")

    for block in retrieval:
        print(f"[{block['split']}] " + "  ".join(f"{r['mode']}: P@5 {r['precision_at_5']:.3f} MRR@5 {r['mrr_at_5']:.3f}"
                                                 for r in block["rows"]))
    print(f"gaps: P {skill_gap['precision']} R {skill_gap['recall']} F1 {skill_gap['f1']} exact {skill_gap['exact_matches']}/{skill_gap['profiles']}")
    print(f"paths: coverage {paths['target_coverage']} unresolved {paths['unresolved_gaps']} dups {paths['duplicate_courses']} "
          f"violations {paths['prerequisite_violations']}")
    print(f"latency: median {lat['median_ms']} ms, p95 {lat['p95_ms']} ms, cold {lat['cold_start_ms']} ms")
    print("edge cases: " + ", ".join(f"{e['name']} {'pass' if e['passed'] else 'FAIL'}" for e in edges))
    print(f"-> {config.EVAL_REPORT_JSON}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "pool":
        write_pool()
    else:
        run()
