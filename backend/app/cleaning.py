"""Deterministic cleaning of the raw course CSV into canonical course records.

Pure functions only: no model, no network. Used by scripts/prepare_data.py and the tests.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from collections import Counter
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

DIFFICULTIES = ("Beginner", "Intermediate", "Advanced", "Mixed", "Unknown")
DESCRIPTION_QUALITIES = ("Unreviewed", "Reviewed", "Suspect", "Missing")

_WS = re.compile(r"[ \t ]+")
# Module activity counts glued into descriptions by the scraper: "8 videos9 readings4 quizzes2 assignments".
_ACTIVITY = re.compile(
    r"(?:\b|(?<=\D))\d+\s*(?:videos?|readings?|quizzes|quiz|assignments?|discussion prompts?|app items?|"
    r"plugins?|ungraded labs?|labs?|peer reviews?|programming assignments?|practice exercises?|"
    r"teammate reviews?|ungraded plugins?)(?![a-z])",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and value.strip() in ("", "nan", "NaN", "None")


def clean_text(value: Any) -> str | None:
    if is_missing(value):
        return None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(_WS.sub(" ", line).strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def parse_skill_list(raw: Any) -> list[str]:
    """Parse the string-encoded skill list safely (JSON or Python literal, never eval)."""
    if is_missing(raw):
        return []
    if isinstance(raw, list):
        items = raw
    else:
        text = str(raw).strip()
        try:
            items = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            try:
                items = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return []
    if not isinstance(items, (list, tuple)):
        return []
    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            label = _WS.sub(" ", item).strip().strip(".")
            if label:
                out.append(label)
    return out


def clean_description(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    text = _ACTIVITY.sub(" ", text)
    text = "\n".join(_WS.sub(" ", line).strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def summarize(text: str | None, max_chars: int = 420) -> str | None:
    """First paragraph, cut at a sentence boundary within max_chars."""
    if not text:
        return None
    first = text.split("\n\n")[0].strip()
    if len(first) <= max_chars:
        return first
    sentences = _SENTENCE_END.split(first)
    out = ""
    for sentence in sentences:
        if len(out) + len(sentence) + 1 > max_chars:
            break
        out = f"{out} {sentence}".strip()
    if not out:
        cut = first[:max_chars].rsplit(" ", 1)[0]
        out = cut.rstrip(",;:") + "..."
    return out


def first_words(text: str | None, n: int) -> str:
    if not text:
        return ""
    return " ".join(text.split()[:n])


def parse_rating(value: Any) -> float | None:
    if is_missing(value):
        return None
    try:
        rating = float(str(value).strip())
    except ValueError:
        return None
    return rating if 0.0 <= rating <= 5.0 else None


def parse_count(value: Any) -> int | None:
    if is_missing(value):
        return None
    text = str(value).strip().replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number >= 0 else None


def parse_difficulty(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return "Unknown"
    low = text.lower()
    for level in ("Beginner", "Intermediate", "Advanced", "Mixed"):
        if low.startswith(level.lower()):
            return level
    return "Unknown"


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower() or "https", parts.netloc.lower(), path.lower(), "", ""))


def course_type_from_url(url: str | None) -> str | None:
    if not url:
        return None
    segment = urlsplit(url).path.strip("/").split("/")[0].lower()
    return {
        "learn": "Course",
        "specializations": "Specialization",
        "professional-certificates": "Professional Certificate",
        "projects": "Guided Project",
    }.get(segment)


def make_course_id(url: str | None, organization: str | None, title: str) -> str:
    basis = canonical_url(url) if url else f"{(organization or '').lower().strip()}|{title.lower().strip()}"
    return "c" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10]


class SkillNormalizer:
    """Maps raw catalog skill labels to canonical names.

    Explicit aliases win. Other labels keep their most frequent spelling so that
    'data analysis' and 'Data Analysis' become one skill without inventing merges.
    """

    def __init__(self, aliases: dict[str, list[str]], observed_labels: Iterable[str] = ()):
        self.alias_map: dict[str, str] = {}
        for canonical, variants in aliases.items():
            self.alias_map[canonical.casefold()] = canonical
            for variant in variants:
                self.alias_map[_WS.sub(" ", variant).strip().casefold()] = canonical
        spellings: dict[str, Counter] = {}
        for label in observed_labels:
            key = label.casefold()
            spellings.setdefault(key, Counter())[label] += 1
        # Most frequent spelling; ties broken alphabetically for determinism.
        self.spelling = {k: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k, c in spellings.items()}

    def canonical(self, label: str) -> str:
        key = _WS.sub(" ", label).strip().casefold()
        if key in self.alias_map:
            return self.alias_map[key]
        return self.spelling.get(key, _WS.sub(" ", label).strip())

    def normalize_list(self, labels: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for label in labels:
            canonical = self.canonical(label)
            if canonical.casefold() not in seen:
                seen.add(canonical.casefold())
                out.append(canonical)
        return out


class TrackSkillMatcher:
    """Finds evidence that a course teaches a curated track skill.

    Evidence comes from the catalog's own skill tags (after alias normalisation, plus
    documented implied tags such as TensorFlow -> Deep Learning) or from the course title.
    Descriptions are not mined: 'assumes Python' and 'teaches Python' read alike.
    """

    def __init__(self, goal_skills: dict[str, Any]):
        self.skills: dict[str, dict[str, Any]] = goal_skills["skills"]
        self.patterns = {
            name: [re.compile(p, re.IGNORECASE) for p in spec.get("title_patterns", [])]
            for name, spec in self.skills.items()
        }
        self.implied = {name: set(spec.get("implied_by", [])) for name, spec in self.skills.items()}

    def evidence(self, title: str, canonical_skills: list[str]) -> list[dict[str, str]]:
        tags = set(canonical_skills)
        found: list[dict[str, str]] = []
        for name in self.skills:
            if name in tags:
                found.append({"skill": name, "source": "catalog tag", "label": name})
                continue
            implied = sorted(self.implied[name] & tags)
            if implied:
                found.append({"skill": name, "source": "catalog tag", "label": implied[0]})
                continue
            if any(p.search(title) for p in self.patterns[name]):
                found.append({"skill": name, "source": "course title", "label": title})
        return found


PROGRAM_TYPES = ("Specialization", "Professional Certificate")


def flag_shared_descriptions(courses: list[dict[str, Any]]) -> dict[str, int]:
    """Flag descriptions copied across different courses.

    When a program (Specialization / Professional Certificate) shares its text with
    member courses, the program keeps it and the courses are flagged, because the
    text describes the series. Otherwise every course in the group is flagged.
    Only Unreviewed records change; manual overrides win.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for course in courses:
        if course["description"]:
            key = " ".join(course["description"].split())[:400].casefold()
            groups.setdefault(key, []).append(course)
    flagged = 0
    group_count = 0
    for members in groups.values():
        if len({m["title"].casefold() for m in members}) < 2:
            continue
        group_count += 1
        programs = [m for m in members if m["course_type"] in PROGRAM_TYPES]
        for member in members:
            if member["description_quality"] != "Unreviewed":
                continue
            if programs and member in programs:
                continue
            others = [m["title"] for m in members if m is not member]
            if programs:
                note = f"Description is the text of the program '{programs[0]['title']}', not specific to this course."
            else:
                note = f"Description text is identical to {len(others)} other course(s), e.g. '{others[0]}'."
            member["description_quality"] = "Suspect"
            member["quality_notes"].append(note)
            flagged += 1
    return {"groups": group_count, "courses_flagged": flagged}


def build_courses(
    rows: list[dict[str, Any]],
    aliases: dict[str, list[str]],
    goal_skills: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    source_file: str = "input.csv",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Clean raw rows into canonical course records plus a data-quality report."""
    overrides = overrides or {}
    parsed_skills = [parse_skill_list(r.get("Skills")) for r in rows]
    normalizer = SkillNormalizer(aliases, (label for labels in parsed_skills for label in labels))
    matcher = TrackSkillMatcher(goal_skills)

    report: dict[str, Any] = {
        "input_rows": len(rows),
        "dropped": {"missing_title": 0, "duplicate_url": 0, "exact_duplicate": 0},
        "missing": Counter(),
        "difficulty": Counter(),
        "course_type": Counter(),
        "raw_skill_labels": len({label for labels in parsed_skills for label in labels}),
    }
    courses: list[dict[str, Any]] = []
    seen_urls: dict[str, str] = {}
    seen_records: set[tuple] = set()
    seen_ids: set[str] = set()

    for index, (row, raw_skills) in enumerate(zip(rows, parsed_skills)):
        title = clean_text(row.get("title"))
        if not title:
            report["dropped"]["missing_title"] += 1
            continue
        url = clean_text(row.get("URL"))
        organization = clean_text(row.get("Organization"))
        description = clean_description(row.get("Description"))
        fingerprint = (title.casefold(), (organization or "").casefold(), (description or "")[:500])
        if fingerprint in seen_records:
            report["dropped"]["exact_duplicate"] += 1
            continue
        if url:
            key = canonical_url(url)
            if key in seen_urls:
                report["dropped"]["duplicate_url"] += 1
                continue
            seen_urls[key] = title
        seen_records.add(fingerprint)

        course_id = make_course_id(url, organization, title)
        suffix = 1
        while course_id in seen_ids:  # collision handling, deterministic
            suffix += 1
            course_id = make_course_id(url, organization, f"{title}#{suffix}")
        seen_ids.add(course_id)

        skills = normalizer.normalize_list(raw_skills)
        rating = parse_rating(row.get("rating"))
        record = {
            "course_id": course_id,
            "title": title,
            "organization": organization,
            "instructor": clean_text(row.get("Instructor")),
            "description": description,
            "summary": summarize(description),
            "skills": skills,
            "source_skill_labels": raw_skills,
            "track_skills": matcher.evidence(title, skills),
            "difficulty": parse_difficulty(row.get("Level")),
            "rating": rating,
            "num_reviews": parse_count(row.get("num_reviews")) if rating is not None else None,
            "enrolled": parse_count(row.get("enrolled")),
            "duration_text": clean_text(row.get("Schedule")),
            "structure_text": clean_text(row.get("Modules/Courses")),
            "satisfaction_text": clean_text(row.get("Satisfaction Rate")),
            "course_type": course_type_from_url(url),
            "course_url": url,
            "description_quality": "Missing" if description is None else "Unreviewed",
            "quality_notes": [],
            "source_ref": {"file": source_file, "row": index, "source_index": row.get("Unnamed: 0")},
        }
        override = overrides.get(course_id)
        if override:
            for field in ("description_quality",):
                if field in override:
                    record[field] = override[field]
            if override.get("reason"):
                record["quality_notes"].append(override["reason"])
        for field in ("organization", "description", "rating", "duration_text", "course_url"):
            if record[field] is None:
                report["missing"][field] += 1
        if not skills:
            report["missing"]["skills"] += 1
        if record["difficulty"] == "Unknown":
            report["missing"]["difficulty"] += 1
        report["difficulty"][record["difficulty"]] += 1
        report["course_type"][record["course_type"] or "Unknown"] += 1
        courses.append(record)

    report["shared_description"] = flag_shared_descriptions(courses)
    courses.sort(key=lambda c: c["course_id"])
    report["output_courses"] = len(courses)
    report["canonical_skills"] = len({s for c in courses for s in c["skills"]})
    report["courses_with_track_skill"] = sum(1 for c in courses if c["track_skills"])
    track_counts: Counter = Counter()
    track_by_source: Counter = Counter()
    for c in courses:
        for ev in c["track_skills"]:
            track_counts[ev["skill"]] += 1
            track_by_source[ev["source"]] += 1
    report["track_skill_courses"] = dict(sorted(track_counts.items()))
    report["track_skill_evidence_sources"] = dict(track_by_source)
    for key in ("missing", "difficulty", "course_type"):
        report[key] = dict(sorted(report[key].items()))
    return courses, report
