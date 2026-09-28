// Mirrors backend/app/schemas.py. Change both together.

export type Difficulty = 'Beginner' | 'Intermediate' | 'Advanced' | 'Mixed'
export type TrackId = 'machine_learning' | 'data_analytics' | 'cloud_computing'
export type SkillState = 'known' | 'simulated' | 'missing'
export type PrereqStatus = 'met' | 'unmet' | 'unknown'
export type FeedbackLabel = 'relevant' | 'not_relevant' | 'too_advanced' | 'too_basic' | 'already_learned'

export interface Filters {
  difficulty: Difficulty | null
  organization: string | null
  min_rating: number | null
}

export interface RecommendRequest {
  goal: string
  goal_track: TrackId | null
  known_skills: string[]
  excluded_skills: string[]
  simulated_skills: string[]
  filters: Filters
  top_k: number
}

export interface SkillEvidence {
  skill: string
  source: 'catalog tag' | 'course title'
  label: string
  strength: 'primary' | 'listed'
}

export interface Prerequisites {
  status: PrereqStatus
  source: 'course description' | 'curated guidance' | null
  required: string[]
  missing: string[]
  evidence: string | null
}

export interface CourseCard {
  course_id: string
  title: string
  organization: string | null
  difficulty: string
  rating: number | null
  num_reviews: number | null
  enrolled: number | null
  duration_text: string | null
  structure_text: string | null
  course_type: string | null
  course_url: string | null
  summary: string | null
  description_quality: 'Unreviewed' | 'Reviewed' | 'Suspect' | 'Missing'
  quality_notes: string[]
  skills: string[]
  track_skills: SkillEvidence[]
}

export interface Retrieval {
  fused_rank: number
  bm25_rank: number | null
  semantic_rank: number | null
  semantic_similarity: number | null
  matched_terms: string[]
}

export interface Recommendation extends CourseCard {
  rank: number
  retrieval: Retrieval
  prerequisites: Prerequisites
  fills_gaps: string[]
  path_step: number | null
  advisor: { why: string[]; before: string[]; consider: string[] }
}

export interface Profile {
  goal: string
  search_text: string
  track_id: TrackId | null
  track_label: string | null
  track_status: 'detected' | 'selected' | 'ambiguous' | 'unsupported'
  track_candidates: TrackId[]
  confirmed_skills: string[]
  inferred_skills: string[]
  negated_skills: string[]
  excluded_skills: string[]
  simulated_skills: string[]
  effective_skills: string[]
  beginner: boolean
  notes: string[]
}

export interface SkillTile {
  skill: string
  abbr: string
  period: number
  group: 'target' | 'supporting'
  state: SkillState
  course_count: number
  requires: string[]
  reason: string | null
  path_step: number | null
}

export interface SkillGap {
  available: boolean
  reason?: string | null
  track_id?: TrackId | null
  tiles: SkillTile[]
  target_skills: string[]
  supporting_skills: string[]
  known_in_track: string[]
  other_known: string[]
  missing_targets: string[]
  missing_supporting: string[]
  coverage: { covered_now: number; projected: number; total: number } | null
}

export interface PathStep {
  step: number
  course: CourseCard
  new_skills: string[]
  new_skill_evidence: SkillEvidence[]
  prerequisites: Prerequisites
  also_lists: string[]
  notes: string[]
}

export interface LearningPath {
  available: boolean
  reason?: string | null
  steps: PathStep[]
  projected_skills: string[]
  unresolved: { skill: string; reason: string }[]
  complete: boolean
}

export interface ApiWarning {
  code: string
  message: string
}

export interface RecommendResponse {
  request_id: string
  data_version: string
  rules_version: string
  mode: 'hybrid' | 'keyword_only'
  is_simulation: boolean
  filters_applied: Partial<Filters>
  eligible_count: number
  profile: Profile
  courses: Recommendation[]
  skill_gap: SkillGap
  learning_path: LearningPath
  warnings: ApiWarning[]
  timing_ms: number
}

export interface SkillInfo {
  skill: string
  abbr: string
  period: number
  requires: string[]
  reason: string | null
  course_count: number
}

export interface TrackInfo {
  id: TrackId
  label: string
  target_skills: string[]
  supporting_skills: string[]
}

export interface CatalogInfo {
  data_version: string
  rules_version: string
  course_count: number
  tracks: TrackInfo[]
  track_skills: SkillInfo[]
  skills: string[]
  difficulties: string[]
  organizations: { name: string; count: number }[]
  source: Record<string, string>
}

export interface Health {
  status: 'ok' | 'degraded' | 'unavailable'
  mode: 'hybrid' | 'keyword_only' | null
  data_version: string | null
  course_count: number
  model: { name: string; revision: string; loaded: boolean; error: string | null } | null
  message: string
  warnings: string[]
}

export interface EvalModeRow {
  mode: 'bm25' | 'semantic' | 'hybrid'
  precision_at_5: number
  mrr_at_5: number
  queries: number
}

export interface EvaluationReport {
  available: boolean
  message?: string
  created?: string
  conditions?: Record<string, string | number>
  retrieval?: { split: string; rows: EvalModeRow[]; per_query?: unknown[] }[]
  skill_gap?: { profiles: number; precision: number; recall: number; f1: number; exact_matches: number; convention: string }
  paths?: { profiles: number; target_coverage: number; unresolved_gaps: number; duplicate_courses: number; prerequisite_violations: number; notes: string[] }
  latency?: { requests: number; median_ms: number; p95_ms: number; cold_start_ms: number | null; machine: string }
  edge_cases?: { name: string; expected: string; observed: string; passed: boolean }[]
  findings?: string[]
  limitations?: string[]
}
