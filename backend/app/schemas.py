"""Request/response contracts. frontend/src/types.ts mirrors these; change both together."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import config

Difficulty = Literal["Beginner", "Intermediate", "Advanced", "Mixed"]
TrackId = Literal["machine_learning", "data_analytics", "cloud_computing"]
SearchMode = Literal["bm25", "semantic", "hybrid"]
FeedbackLabel = Literal["relevant", "not_relevant", "too_advanced", "too_basic", "already_learned"]
SkillState = Literal["known", "simulated", "missing"]
PrereqStatus = Literal["met", "unmet", "unknown"]
PrereqSource = Literal["course description", "curated guidance"]
EvidenceSource = Literal["catalog tag", "course title"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FiltersIn(Strict):
    difficulty: Optional[Difficulty] = None
    organization: Optional[str] = Field(default=None, max_length=200)
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)

    @field_validator("organization")
    @classmethod
    def blank_is_none(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() or None if v is not None else None


def _clean_skills(values: list[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        v = v.strip()
        if not v:
            continue
        if len(v) > 80:
            raise ValueError("Each skill name must be 80 characters or fewer.")
        if v.casefold() not in {o.casefold() for o in out}:
            out.append(v)
    return out


class RecommendRequest(Strict):
    goal: str = Field(min_length=1, max_length=config.MAX_GOAL_CHARS)
    goal_track: Optional[TrackId] = None
    known_skills: list[str] = Field(default_factory=list, max_length=config.MAX_SKILLS_IN_PROFILE)
    excluded_skills: list[str] = Field(default_factory=list, max_length=config.MAX_SKILLS_IN_PROFILE)
    simulated_skills: list[str] = Field(default_factory=list, max_length=config.MAX_SKILLS_IN_PROFILE)
    filters: FiltersIn = Field(default_factory=FiltersIn)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("goal")
    @classmethod
    def goal_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Describe what you want to learn.")
        return v.strip()

    @field_validator("known_skills", "excluded_skills", "simulated_skills")
    @classmethod
    def clean_skill_lists(cls, v: list[str]) -> list[str]:
        return _clean_skills(v)


class SearchRequest(Strict):
    query: str = Field(min_length=1, max_length=config.MAX_GOAL_CHARS)
    mode: SearchMode = "hybrid"
    filters: FiltersIn = Field(default_factory=FiltersIn)
    top_k: int = Field(default=10, ge=1, le=50)


class FeedbackRequest(Strict):
    course_id: str = Field(min_length=3, max_length=40)
    label: FeedbackLabel
    request_id: Optional[str] = Field(default=None, max_length=64)
    comment: Optional[str] = Field(default=None, max_length=config.MAX_COMMENT_CHARS)
    goal: Optional[str] = Field(default=None, max_length=config.MAX_GOAL_CHARS)
    goal_track: Optional[TrackId] = None
    known_skills: list[str] = Field(default_factory=list, max_length=config.MAX_SKILLS_IN_PROFILE)
    simulated_skills: list[str] = Field(default_factory=list, max_length=config.MAX_SKILLS_IN_PROFILE)
    is_simulation: bool = False


# Responses -------------------------------------------------------------------


class Warning_(BaseModel):
    code: str
    message: str


class SkillEvidence(BaseModel):
    skill: str
    source: EvidenceSource
    label: str
    strength: Literal["primary", "listed"] = "primary"


class Prerequisites(BaseModel):
    status: PrereqStatus
    source: Optional[PrereqSource] = None
    required: list[str] = []
    missing: list[str] = []
    evidence: Optional[str] = None


class Advisor(BaseModel):
    why: list[str]
    before: list[str]
    consider: list[str]


class Retrieval(BaseModel):
    fused_rank: int
    bm25_rank: Optional[int] = None
    semantic_rank: Optional[int] = None
    semantic_similarity: Optional[float] = None
    matched_terms: list[str] = []


class CourseCard(BaseModel):
    course_id: str
    title: str
    organization: Optional[str]
    difficulty: str
    rating: Optional[float]
    num_reviews: Optional[int]
    enrolled: Optional[int]
    duration_text: Optional[str]
    structure_text: Optional[str]
    course_type: Optional[str]
    course_url: Optional[str]
    summary: Optional[str]
    description_quality: str
    quality_notes: list[str]
    skills: list[str]
    track_skills: list[SkillEvidence]


class Recommendation(CourseCard):
    rank: int
    retrieval: Retrieval
    prerequisites: Prerequisites
    fills_gaps: list[str]
    path_step: Optional[int] = None
    advisor: Advisor


class Profile(BaseModel):
    goal: str
    search_text: str
    track_id: Optional[TrackId]
    track_label: Optional[str]
    track_status: Literal["detected", "selected", "ambiguous", "unsupported"]
    track_candidates: list[TrackId]
    confirmed_skills: list[str]
    inferred_skills: list[str]
    negated_skills: list[str]
    excluded_skills: list[str]
    simulated_skills: list[str]
    effective_skills: list[str]
    beginner: bool
    notes: list[str]


class SkillTile(BaseModel):
    skill: str
    abbr: str
    period: int
    group: Literal["target", "supporting"]
    state: SkillState
    course_count: int
    requires: list[str]
    reason: Optional[str]
    path_step: Optional[int] = None


class Coverage(BaseModel):
    covered_now: int
    projected: int
    total: int


class SkillGap(BaseModel):
    available: bool
    reason: Optional[str] = None
    track_id: Optional[TrackId] = None
    tiles: list[SkillTile] = []
    target_skills: list[str] = []
    supporting_skills: list[str] = []
    known_in_track: list[str] = []
    other_known: list[str] = []
    missing_targets: list[str] = []
    missing_supporting: list[str] = []
    coverage: Optional[Coverage] = None


class PathStep(BaseModel):
    step: int
    course: CourseCard
    new_skills: list[str]
    new_skill_evidence: list[SkillEvidence]
    prerequisites: Prerequisites
    also_lists: list[str]
    notes: list[str]


class Unresolved(BaseModel):
    skill: str
    reason: str


class LearningPath(BaseModel):
    available: bool
    reason: Optional[str] = None
    steps: list[PathStep] = []
    projected_skills: list[str] = []
    unresolved: list[Unresolved] = []
    complete: bool = False


class RecommendResponse(BaseModel):
    request_id: str
    data_version: str
    rules_version: str
    mode: Literal["hybrid", "keyword_only"]
    is_simulation: bool
    filters_applied: dict
    eligible_count: int
    profile: Profile
    courses: list[Recommendation]
    skill_gap: SkillGap
    learning_path: LearningPath
    warnings: list[Warning_]
    timing_ms: float


class SearchResult(BaseModel):
    course: CourseCard
    retrieval: Retrieval


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    data_version: str
    eligible_count: int
    results: list[SearchResult]
    timing_ms: float


class FeedbackResponse(BaseModel):
    feedback_id: int
    stored_at: str


class SkillInfo(BaseModel):
    skill: str
    abbr: str
    period: int
    requires: list[str]
    reason: Optional[str]
    course_count: int


class TrackInfo(BaseModel):
    id: TrackId
    label: str
    target_skills: list[str]
    supporting_skills: list[str]


class OrganizationCount(BaseModel):
    name: str
    count: int


class CatalogResponse(BaseModel):
    data_version: str
    rules_version: str
    course_count: int
    tracks: list[TrackInfo]
    track_skills: list[SkillInfo]
    skills: list[str]
    difficulties: list[str]
    organizations: list[OrganizationCount]
    source: dict


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    mode: Optional[Literal["hybrid", "keyword_only"]]
    data_version: Optional[str]
    course_count: int
    model: Optional[dict]
    message: str
    warnings: list[str]
