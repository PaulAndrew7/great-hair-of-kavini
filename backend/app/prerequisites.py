"""Course prerequisite status with an explicit source for every relation.

Two sources exist:
- course description: a reviewed entry in data/rules/course_prerequisites.json quoting the catalog text;
- curated guidance: derived from the skill dependencies of the track skills the course teaches.
A course that teaches no modelled skill and has no reviewed entry is 'unknown', never 'none'.
"""
from __future__ import annotations

import json
from typing import Any

from . import config
from .skills import SkillModel


def load_reviewed() -> dict[str, dict[str, Any]]:
    if not config.COURSE_PREREQS_JSON.exists():
        return {}
    data = json.loads(config.COURSE_PREREQS_JSON.read_text(encoding="utf-8"))
    return {entry["course_id"]: entry for entry in data.get("entries", [])}


class PrereqModel:
    def __init__(self, skills: SkillModel, reviewed: dict[str, dict[str, Any]]):
        self.skills = skills
        self.reviewed = reviewed

    @staticmethod
    def primary(course: dict[str, Any]) -> list[str]:
        """Track skills that are the course's main subject; falls back to every listed skill."""
        primary = [ev["skill"] for ev in course["track_skills"] if ev.get("strength", "primary") == "primary"]
        return primary or [ev["skill"] for ev in course["track_skills"]]

    def requirements(self, course: dict[str, Any]) -> tuple[list[str], str | None, str | None]:
        """(required skills, source, evidence). source None means unknown."""
        entry = self.reviewed.get(course["course_id"])
        if entry:
            return self.skills.ordered(entry["requires"]), "course description", entry.get("evidence")
        taught = set(self.primary(course))
        if not taught:
            return [], None, None
        required: set[str] = set()
        for skill in taught:
            required.update(self.skills.deps.get(skill, []))
        required -= taught
        return self.skills.ordered(required), "curated guidance", None

    def status(self, course: dict[str, Any], have: set[str]) -> dict[str, Any]:
        required, source, evidence = self.requirements(course)
        if source is None:
            return {"status": "unknown", "source": None, "required": [], "missing": [], "evidence": None}
        missing = [s for s in required if s not in have]
        return {
            "status": "unmet" if missing else "met",
            "source": source,
            "required": required,
            "missing": missing,
            "evidence": evidence,
        }
