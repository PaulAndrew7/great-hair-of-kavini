"""Skill vocabulary, goal parsing, track detection, prerequisite closure and gap analysis."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from .cleaning import SkillNormalizer

# Clause boundaries: sentence ends, "but", and "and"/"," when a new first-person clause starts.
_CLAUSE_SPLIT = re.compile(
    r"[.;!?\n]+|,?\s+but\s+|\s+however\s+|,\s*(?=(?:i|i'm|im|help|now)\b)|\s+and\s+(?=(?:i|i'm|im|want|would|need|now|help)\b)",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(?:don'?t|do not|doesn'?t|never|no|not|haven'?t|have not|hasn'?t|can'?t|cannot|without|zero|new to|lack|unfamiliar)\b",
    re.IGNORECASE,
)
_KNOWN = re.compile(
    r"\b(?:i\s+(?:already\s+)?(?:know|knew|use|used|have\s+(?:learn(?:ed|t)|studied|used|done|taken|worked\s+with)|"
    r"(?:am|'m)\s+(?:good|comfortable|familiar|experienced|proficient|confident)\s+(?:at|with|in)|can\s+(?:use|code|write|program|do))|"
    r"i'?m\s+(?:good|comfortable|familiar|experienced|proficient|confident)\s+(?:at|with|in)|"
    r"(?:experience|background|familiar(?:ity)?|comfortable|proficient|skilled)\s+(?:in|with|at)|known\s+skills?|know(?:ing)?\s+how\s+to)\b",
    re.IGNORECASE,
)
_TARGET = re.compile(
    r"\b(?:want|wish|hope|plan|learn|study|move|get into|switch|transition|become|master|pick up|interested in|"
    r"help me|teach me|suggest|recommend|path|career in|go into)\b",
    re.IGNORECASE,
)
_BEGINNER = re.compile(r"\b(?:from (?:the )?(?:basics|scratch|zero|the beginning)|beginner|complete novice|never (?:coded|programmed))\b", re.I)

# Extra surface forms the goal parser recognises beyond the alias file.
EXTRA_SURFACE = {
    "Python": ["python"],
    "SQL": ["sql", "databases"],
    "Spreadsheets": ["excel", "spreadsheets", "google sheets"],
    "Statistics": ["stats", "statistics", "probability"],
    "Linear Algebra": ["linear algebra", "matrices"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "neural networks", "neural nets"],
    "Cloud Platforms": ["aws", "azure", "gcp", "google cloud"],
    "Containers": ["docker", "containers"],
    "Kubernetes": ["kubernetes", "k8s"],
    "BI Dashboards": ["tableau", "power bi", "dashboards"],
    "Data Visualization": ["data visualization", "data visualisation", "visualization", "charts"],
    "Git": ["git", "github"],
    "R": ["r programming", "rstudio"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js"],
    "HTML": ["html"],
    "CSS": ["css"],
    "C++": ["c++"],
}
# Aliases too generic to count as a skill mention in free text.
AMBIGUOUS_SURFACE = {"cloud", "visualization", "probability", "dashboard", "dashboards", "networking", "matrices", "charts", "r"}


class CycleError(ValueError):
    pass


@dataclass
class GoalParse:
    known: list[str] = field(default_factory=list)
    negated: list[str] = field(default_factory=list)
    mentioned: list[str] = field(default_factory=list)
    target_text: str = ""
    beginner: bool = False


@dataclass
class TrackMatch:
    track_id: str | None
    status: str  # detected | selected | ambiguous | unsupported | generated
    candidates: list[str]
    scores: dict[str, int] = field(default_factory=dict)  # detection cues matched per track


class SkillModel:
    def __init__(self, goal_skills: dict[str, Any], aliases: dict[str, list[str]], observed_labels: list[str]):
        self.version = goal_skills.get("version", "unknown")
        self.skills: dict[str, dict[str, Any]] = goal_skills["skills"]
        self.tracks: dict[str, dict[str, Any]] = goal_skills["tracks"]
        self.normalizer = SkillNormalizer(aliases, observed_labels)
        self.deps: dict[str, list[str]] = {s: [] for s in self.skills}
        self.dep_reason: dict[str, str] = {}
        self.origin: dict[str, str] = {s: "curated" for s in self.skills}  # "ai" for skills an AI track added
        for dep in goal_skills["dependencies"]:
            for name in [dep["skill"], *dep["requires"]]:
                if name not in self.skills:
                    raise ValueError(f"Dependency mentions unknown skill '{name}'")
            self.deps[dep["skill"]] = list(dep["requires"])
            self.dep_reason[dep["skill"]] = dep.get("reason", "")
        for track in self.tracks.values():
            for name in track["target_skills"]:
                if name not in self.skills:
                    raise ValueError(f"Track target '{name}' is not a defined skill")
        self.period = self._periods()
        self._forms = self._surface_forms(aliases)
        self._surface = self._compile_surface(self._forms)
        self._extra_names: dict[str, str] = {}
        self._detect = {tid: [re.compile(p, re.I) for p in t["detect"]] for tid, t in self.tracks.items()}

    # Graph -------------------------------------------------------------------
    def _periods(self) -> dict[str, int]:
        period: dict[str, int] = {}
        visiting: set[str] = set()

        def visit(skill: str, trail: tuple[str, ...]) -> int:
            if skill in period:
                return period[skill]
            if skill in visiting:
                raise CycleError(" -> ".join((*trail, skill)))
            visiting.add(skill)
            value = 1 + max((visit(d, (*trail, skill)) for d in self.deps.get(skill, [])), default=0)
            visiting.discard(skill)
            period[skill] = value
            return value

        for skill in self.skills:
            visit(skill, ())
        return period

    def closure(self, skills: list[str] | set[str]) -> set[str]:
        out: set[str] = set()
        stack = [s for s in skills if s in self.skills]
        while stack:
            skill = stack.pop()
            if skill in out:
                continue
            out.add(skill)
            stack.extend(self.deps.get(skill, []))
        return out

    def track_required(self, track_id: str) -> set[str]:
        """Every skill a track covers: its targets, any declared foundations, and their prerequisites."""
        track = self.tracks[track_id]
        return self.closure([*track["target_skills"], *track.get("foundations", [])])

    def ordered(self, skills: set[str] | list[str]) -> list[str]:
        return sorted(skills, key=lambda s: (self.period.get(s, 99), s))

    # Vocabulary ----------------------------------------------------------------
    def _surface_forms(self, aliases: dict[str, list[str]]) -> dict[str, str]:
        forms: dict[str, str] = {}
        for canonical, variants in aliases.items():
            for v in [canonical, *variants]:
                forms.setdefault(v.casefold(), canonical)
        for canonical, variants in EXTRA_SURFACE.items():
            for v in variants:
                forms[v.casefold()] = canonical
        for s in self.skills:
            forms.setdefault(s.casefold(), s)
        return forms

    @staticmethod
    def _compile_surface(forms: dict[str, str]) -> list[tuple[re.Pattern, str]]:
        patterns = []
        for form in sorted(forms, key=len, reverse=True):
            if form in AMBIGUOUS_SURFACE:
                continue
            patterns.append((re.compile(r"(?<![\w+#])" + re.escape(form) + r"(?![\w+#])", re.I), forms[form]))
        return patterns

    def canonical(self, label: str) -> str:
        label = label.strip()
        if label.casefold() in self._extra_names:
            return self._extra_names[label.casefold()]
        for pattern, canonical in self._surface:
            if pattern.fullmatch(label):
                return canonical
        return self.normalizer.canonical(label)

    def find_mentions(self, text: str) -> list[str]:
        out: list[str] = []
        for _, canonical in self._mention_spans(text):
            if canonical not in out:
                out.append(canonical)
        return out

    # Goal parsing ----------------------------------------------------------------
    def _mention_spans(self, text: str) -> list[tuple[int, str]]:
        taken = [False] * len(text)
        found: list[tuple[int, str]] = []
        for pattern, canonical in self._surface:
            for m in pattern.finditer(text):
                if any(taken[m.start():m.end()]):
                    continue
                for i in range(m.start(), m.end()):
                    taken[i] = True
                found.append((m.start(), canonical))
        return sorted(found)

    @staticmethod
    def _cues(clause: str) -> list[tuple[int, str]]:
        """Polarity cues in a clause: 'known', 'negated' or 'target', by position."""
        cues: list[tuple[int, str]] = []
        for m in _KNOWN.finditer(clause):
            negated = _NEGATION.search(clause[max(0, m.start() - 14):m.start()])
            cues.append((m.start(), "negated" if negated else "known"))
        for m in _NEGATION.finditer(clause):
            cues.append((m.start(), "negated"))
        for m in _TARGET.finditer(clause):
            cues.append((m.start(), "target"))
        return sorted(cues)

    def parse_goal(self, goal: str) -> GoalParse:
        """Each skill mention takes the polarity of the nearest cue before it in its clause.

        "I know Python, not sure about SQL" -> Python known, SQL negated.
        "I don't know Python" -> Python negated (never marked known).
        Mentions with no cue, or after a target cue ("want", "learn", "move into"), are goal topics.
        """
        parse = GoalParse(beginner=bool(_BEGINNER.search(goal)))
        target_parts: list[str] = []
        for clause in _CLAUSE_SPLIT.split(goal):
            clause = clause.strip(" ,")
            if not clause:
                continue
            cues = self._cues(clause)
            for pos, skill in self._mention_spans(clause):
                before = [kind for cpos, kind in cues if cpos <= pos]
                kind = before[-1] if before else "target"
                bucket = {"known": parse.known, "negated": parse.negated, "target": parse.mentioned}[kind]
                if skill not in bucket:
                    bucket.append(skill)
            first_target = next((cpos for cpos, kind in cues if kind == "target"), None)
            if first_target is not None:
                target_parts.append(clause[first_target:])
            elif not cues:
                target_parts.append(clause)
        parse.known = [s for s in parse.known if s not in parse.negated]
        parse.target_text = ". ".join(target_parts).strip() or goal.strip()
        return parse

    def detect_track(self, goal_parse: GoalParse, full_goal: str, explicit: str | None) -> TrackMatch:
        if explicit:
            return TrackMatch(explicit, "selected", [explicit])
        for text in (goal_parse.target_text, full_goal):
            scores = {tid: sum(1 for p in pats if p.search(text)) for tid, pats in self._detect.items()}
            best = max(scores.values())
            if best == 0:
                continue
            top = sorted([tid for tid, s in scores.items() if s == best])
            if len(top) == 1:
                return TrackMatch(top[0], "detected", top, scores)
            return TrackMatch(None, "ambiguous", top, scores)
        return TrackMatch(None, "unsupported", [])

    # AI-drafted tracks -------------------------------------------------------------
    def with_track(self, track_id: str, track: dict[str, Any], new_skills: dict[str, dict[str, Any]],
                   deps: dict[str, list[str]], reasons: dict[str, str]) -> "SkillModel":
        """A copy that also knows one extra track and the new skills it adds.

        The curated graph is left as it is: new skills may build on curated ones, never the other way round, so a
        cycle can only form among new skills (the caller removes those edges first). The goal parser learns the new
        names, so "I know React" counts once a track adds React.
        """
        out = copy.copy(self)
        out.skills = {**self.skills, **new_skills}
        out.tracks = {**self.tracks, track_id: track}
        out.deps = {**self.deps, **{s: list(deps.get(s, [])) for s in new_skills}}
        out.dep_reason = {**self.dep_reason, **{s: r for s, r in reasons.items() if s in new_skills and r}}
        out.origin = {**self.origin, **{s: "ai" for s in new_skills}}
        out.period = out._periods()
        forms = dict(self._forms)
        for name in new_skills:
            forms.setdefault(name.casefold(), name)
        out._forms = forms
        out._surface = self._compile_surface(forms)
        out._extra_names = {**self._extra_names, **{name.casefold(): name for name in new_skills}}
        out._detect = self._detect
        return out

    # Gaps ----------------------------------------------------------------------
    def gap(self, track_id: str, confirmed: set[str], simulated: set[str]) -> dict[str, Any]:
        track = self.tracks[track_id]
        targets = list(track["target_skills"])
        required = self.track_required(track_id)
        supporting = required - set(targets)
        effective = confirmed | simulated

        def state(skill: str) -> str:
            if skill in confirmed:
                return "known"
            if skill in simulated:
                return "simulated"
            return "missing"

        return {
            "targets": targets,
            "supporting": self.ordered(supporting),
            "required": self.ordered(required),
            "state": {s: state(s) for s in required},
            "missing": self.ordered(required - effective),
            "missing_targets": [s for s in self.ordered(set(targets)) if s not in effective],
            "missing_supporting": self.ordered(supporting - effective),
            "known_in_track": self.ordered((required & effective)),
            "other_known": sorted(effective - required),
        }
