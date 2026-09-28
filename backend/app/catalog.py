"""Load the processed catalog and index artifacts, and refuse to serve misaligned ones."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from . import config
from .cleaning import TrackSkillMatcher, first_words


class CatalogError(RuntimeError):
    """Artifacts are missing or inconsistent; the service must not answer from them."""


def embedding_text(course: dict[str, Any]) -> str:
    """Recipe recorded in the manifest: title first, then skills, then validated description."""
    parts = [course["title"].rstrip(".") + "."]
    if course["skills"]:
        parts.append("Skills: " + ", ".join(course["skills"]) + ".")
    if course["description"] and course["description_quality"] not in ("Missing", "Suspect"):
        parts.append(first_words(course["description"], config.EMBED_DESCRIPTION_WORDS))
    return " ".join(parts)


def bm25_text(course: dict[str, Any]) -> str:
    """Title weighted x3 and skills x2 by repetition; suspect or missing descriptions excluded."""
    title = course["title"]
    skills = " ".join(course["skills"])
    body = ""
    if course["description"] and course["description_quality"] not in ("Missing", "Suspect"):
        body = first_words(course["description"], 300)
    return " ".join([title, title, title, skills, skills, course.get("organization") or "", body])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class Catalog:
    courses: list[dict[str, Any]]
    embeddings: np.ndarray
    manifest: dict[str, Any]
    goal_skills: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.position = {c["course_id"]: i for i, c in enumerate(self.courses)}
        matcher = TrackSkillMatcher(self.goal_skills)
        self.skill_courses: dict[str, list[int]] = {name: [] for name in self.goal_skills["skills"]}
        for i, course in enumerate(self.courses):
            # Recomputed at startup so edits to goal_skills.json need only a restart.
            course["track_skills"] = matcher.evidence(course["title"], course["skills"])
            for ev in course["track_skills"]:
                self.skill_courses[ev["skill"]].append(i)
        self.difficulty = np.array([c["difficulty"] for c in self.courses])
        self.rating = np.array([c["rating"] if c["rating"] is not None else np.nan for c in self.courses], dtype=float)
        self.org_key = np.array([(c["organization"] or "").casefold() for c in self.courses])
        orgs = Counter(c["organization"] for c in self.courses if c["organization"])
        self.organizations = sorted(orgs.items(), key=lambda kv: (-kv[1], kv[0]))

    @property
    def data_version(self) -> str:
        return self.manifest["data_version"]

    def get(self, course_id: str) -> dict[str, Any] | None:
        pos = self.position.get(course_id)
        return None if pos is None else self.courses[pos]


def load_catalog() -> Catalog:
    required = [config.MANIFEST_JSON, config.COURSES_JSON, config.COURSE_IDS_JSON, config.EMBEDDINGS_NPY, config.GOAL_SKILLS_JSON]
    missing = [str(p.relative_to(config.REPO_ROOT)) for p in required if not p.exists()]
    if missing:
        raise CatalogError(
            "Missing artifacts: " + ", ".join(missing) + ". Run scripts/prepare_data.py then scripts/build_index.py."
        )
    manifest = json.loads(config.MANIFEST_JSON.read_text(encoding="utf-8"))
    if _sha256(config.COURSES_JSON) != manifest["courses_sha256"]:
        raise CatalogError("courses.json does not match the index manifest. Re-run scripts/build_index.py.")
    if _sha256(config.COURSE_IDS_JSON) != manifest["course_ids_sha256"]:
        raise CatalogError("course_ids.json does not match the index manifest. Re-run scripts/build_index.py.")
    courses = json.loads(config.COURSES_JSON.read_text(encoding="utf-8"))
    ids = json.loads(config.COURSE_IDS_JSON.read_text(encoding="utf-8"))
    embeddings = np.load(config.EMBEDDINGS_NPY)
    if [c["course_id"] for c in courses] != ids:
        raise CatalogError("Course order differs from the embedding row order. Re-run scripts/build_index.py.")
    if embeddings.shape[0] != len(ids) or list(embeddings.shape) != manifest["embeddings_shape"]:
        raise CatalogError(
            f"Embedding rows ({embeddings.shape[0]}) do not match courses ({len(ids)}). Re-run scripts/build_index.py."
        )
    if len(set(ids)) != len(ids):
        raise CatalogError("Duplicate course IDs in the catalog.")

    goal_skills = json.loads(config.GOAL_SKILLS_JSON.read_text(encoding="utf-8"))
    warnings: list[str] = []
    for path in (config.SKILL_ALIASES_JSON, config.COURSE_OVERRIDES_JSON):
        recorded = manifest.get("rules", {}).get(path.name)
        if recorded and path.exists() and _sha256(path)[:12] != recorded:
            warnings.append(f"{path.name} changed since the index was built; re-run prepare_data.py and build_index.py.")
    return Catalog(courses=courses, embeddings=embeddings.astype(np.float32), manifest=manifest,
                   goal_skills=goal_skills, warnings=warnings)
