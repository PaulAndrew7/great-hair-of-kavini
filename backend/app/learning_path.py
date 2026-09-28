"""Deterministic greedy learning path over the whole filtered catalog (plan section 5.4)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from . import config
from .catalog import Catalog
from .prerequisites import PrereqModel
from .skills import SkillModel

# Levels that suit a skill at each period (dependency depth). Penalties rise with distance.
_DIFFICULTY_PENALTY = {
    1: {"Beginner": 0, "Mixed": 1, "Unknown": 1, "Intermediate": 1, "Advanced": 3},
    2: {"Beginner": 0, "Intermediate": 0, "Mixed": 1, "Unknown": 1, "Advanced": 2},
    3: {"Intermediate": 0, "Advanced": 0, "Beginner": 1, "Mixed": 1, "Unknown": 1},
}
SKILL_REL_WEIGHT, GOAL_REL_WEIGHT, DIFFICULTY_WEIGHT, QUALITY_WEIGHT = 0.65, 0.35, 0.05, 0.05


@dataclass
class PathContext:
    catalog: Catalog
    skills: SkillModel
    prereqs: PrereqModel
    skill_vectors: dict[str, np.ndarray] | None  # None in keyword-only mode


def difficulty_penalty(difficulty: str, period: int, beginner: bool) -> int:
    table = _DIFFICULTY_PENALTY[min(period, 3)]
    penalty = table.get(difficulty, 1)
    if beginner and difficulty == "Advanced":
        penalty += 1
    return penalty


def build_path(
    ctx: PathContext,
    track_id: str,
    effective: set[str],
    eligible: np.ndarray,
    goal_vec: np.ndarray | None,
    beginner: bool,
    filters_active: bool,
) -> dict[str, Any]:
    targets = ctx.skills.tracks[track_id]["target_skills"]
    required = ctx.skills.closure(targets)
    covered = set(effective)
    missing = set(required) - covered
    steps: list[dict[str, Any]] = []
    selected: set[int] = set()
    stuck: dict[str, str] = {}

    while missing and len(steps) < config.MAX_PATH_STEPS:
        learnable = {s for s in missing if set(ctx.skills.deps.get(s, [])) <= covered}
        if not learnable:
            break
        best: tuple | None = None
        for skill in ctx.skills.ordered(learnable):
            for pos in ctx.catalog.skill_courses.get(skill, []):
                if pos in selected or not eligible[pos]:
                    continue
                course = ctx.catalog.courses[pos]
                primary = {ev["skill"] for ev in course["track_skills"] if ev.get("strength", "primary") == "primary"}
                gain = primary & learnable  # a skill the course only lists in passing is never credited
                if not gain:
                    continue
                prereq = ctx.prereqs.status(course, covered)
                if prereq["status"] == "unmet":
                    continue  # never schedule a course before its modelled prerequisites
                tier = 0 if prereq["status"] == "met" else 1
                period = min(ctx.skills.period[s] for s in gain)
                penalty = difficulty_penalty(course["difficulty"], period, beginner)
                score = -DIFFICULTY_WEIGHT * penalty
                if ctx.skill_vectors is not None:
                    vec = ctx.catalog.embeddings[pos]
                    skill_rel = max(float(vec @ ctx.skill_vectors[s]) for s in gain)
                    goal_rel = float(vec @ goal_vec) if goal_vec is not None else 0.0
                    score += SKILL_REL_WEIGHT * skill_rel + GOAL_REL_WEIGHT * goal_rel
                rating = course["rating"]
                # Weak quality signal: a 3.7-rated course should not beat a 4.7 one on a hair of relevance.
                quality = min(max((rating - 4.5) if rating is not None else -0.3, -1.0), 0.4)
                score += QUALITY_WEIGHT * quality
                key = (tier, -len(gain), -round(score, 4), -(rating or 0.0), course["course_id"])
                if best is None or key < best[0]:
                    best = (key, pos, gain, prereq)
        if best is None:
            for skill in learnable:
                stuck[skill] = "no_course"
            missing -= learnable
            continue
        _, pos, gain, prereq = best
        course = ctx.catalog.courses[pos]
        also = [ev["skill"] for ev in course["track_skills"] if ev["skill"] not in gain]
        notes = []
        known_overlap = [s for s in also if s in effective]
        if known_overlap:
            notes.append("Also covers " + ", ".join(known_overlap) + ", which you already have.")
        passing = [ev["skill"] for ev in course["track_skills"]
                   if ev.get("strength") == "listed" and ev["skill"] not in covered]
        if passing:
            notes.append("Also tags " + ", ".join(passing) + ", but is not mainly about it, so it is not counted here.")
        if prereq["status"] == "unknown":
            notes.append("Prerequisites for this course are not verified.")
        steps.append({
            "step": len(steps) + 1,
            "pos": pos,
            "new_skills": ctx.skills.ordered(gain),
            "new_skill_evidence": [ev for ev in course["track_skills"] if ev["skill"] in gain],
            "prerequisites": prereq,
            "also_lists": also,
            "notes": notes,
        })
        selected.add(pos)
        covered |= gain
        missing -= gain

    unresolved = []
    for skill in ctx.skills.ordered(set(required) - covered):
        blockers = [d for d in ctx.skills.deps.get(skill, []) if d not in covered]
        if stuck.get(skill) == "no_course" or not any(
            eligible[p] for p in ctx.catalog.skill_courses.get(skill, [])
        ):
            reason = f"No course in the catalog teaches {skill}"
            if filters_active and ctx.catalog.skill_courses.get(skill):
                reason += " with the current filters"
            reason += "."
        elif blockers:
            reason = "Waits on " + ", ".join(blockers) + ", which the path does not cover yet."
        elif len(steps) >= config.MAX_PATH_STEPS:
            reason = f"The path stops at {config.MAX_PATH_STEPS} courses."
        else:
            reason = f"Every course listing {skill} expects skills this path does not cover."
        unresolved.append({"skill": skill, "reason": reason})

    return {
        "steps": steps,
        "projected_skills": ctx.skills.ordered(covered & required),
        "unresolved": unresolved,
        "complete": not unresolved,
    }
