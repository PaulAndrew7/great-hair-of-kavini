// Mirrors backend/app/schemas.py. Change both together.

export type Difficulty = 'Beginner' | 'Intermediate' | 'Advanced' | 'Mixed'
export type TrackId = 'machine_learning' | 'data_analytics' | 'cloud_computing'
/** 'custom' is an AI-drafted track; it only appears in responses, never in requests. */
export type ProfileTrackId = TrackId | 'custom'
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
  source: 'course description' | 'curated guidance' | 'AI-drafted guidance' | null
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
  /** Calibrated estimate that this result is relevant (not a similarity percentage). */
  confidence: number | null
  confidence_band: 'high' | 'medium' | 'low' | null
  cosine: number | null
  keyword_coverage: number | null
  query_terms: number
  matched_query_terms: string[]
  channels: number
  judged_relevant: boolean | null
  judgment_reason: string | null
}

export interface Recommendation extends CourseCard {
  rank: number
  retrieval: Retrieval
  prerequisites: Prerequisites
  fills_gaps: string[]
  path_step: number | null
  advisor: { why: string[]; before: string[]; consider: string[] }
}

export interface AiTrack {
  model: string
  base_track: TrackId | null
  base_label: string | null
  new_skills: string[]
  left_out: string[]
  unteachable: string[]
  notes: string[]
}

export interface Profile {
  goal: string
  search_text: string
  track_id: ProfileTrackId | null
  track_label: string | null
  track_status: 'detected' | 'selected' | 'ambiguous' | 'unsupported' | 'generated'
  track_candidates: TrackId[]
  ai_track: AiTrack | null
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
  origin: 'curated' | 'ai'
  path_step: number | null
}

export interface SkillGap {
  available: boolean
  reason?: string | null
  track_id?: ProfileTrackId | null
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
  match: { skill_similarity: number | null; goal_similarity: number | null; evidence: 'course title' | 'catalog tag' }
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
  evaluation: QueryEvaluation
  warnings: ApiWarning[]
  timing_ms: number
}

export interface ReliabilityBin { lo: number; hi: number; n: number; predicted: number; observed: number }

export interface CalibrationSummary {
  labels: number
  queries: number
  base_rate: number
  features: string[]
  method: string
  brier: number
  baseline_brier: number
  log_loss: number
  accuracy: number
  auc: number | null
  reliability: ReliabilityBin[]
}

/** Per-request evaluation: estimated (calibrated), measured (labelled queries only) and checked (rules). */
export interface QueryEvaluation {
  retrieval: {
    extrapolated: boolean
    shown: number
    k: number
    expected_relevant: number | null
    expected_precision: number | null
    top_confidence: number | null
    min_confidence: number | null
    channel_agreement: number | null
    agreement_depth: number
    query_terms: string[]
    unmatched_terms: string[]
  }
  calibration: CalibrationSummary | null
  ground_truth: {
    query_id: string; split: string; judged: number; relevant: number; shown: number
    precision_at_k: number; rr_at_k: number; note: string
  } | null
  track: {
    status: string
    confidence: 'certain' | 'high' | 'medium' | 'low' | 'none' | 'drafted'
    scores: Record<string, number>
    margin: number
    explanation: string
  }
  skill_gap: {
    profile_id: string; precision: number; recall: number; f1: number; exact: boolean
    false_positives: string[]; false_negatives: string[]
  } | null
  path: {
    steps: number
    target_coverage_now: number | null
    target_coverage_projected: number | null
    unresolved: number
    duplicates: number
    prerequisite_violations: number
    violations: string[]
    unverified_steps: number
    mean_skill_similarity: number | null
  } | null
  reference: {
    created: string | null; mode: string; precision_at_5: number | null; mrr_at_5: number | null; queries: number | null
    gap_f1: number | null; gap_profiles: number | null; path_target_coverage: number | null
    path_prerequisite_violations: number | null
  } | null
  notes: string[]
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
  llm?: { enabled: boolean; model: string; gateway: string } | null
  message: string
  warnings: string[]
}

export interface EvalModeRow {
  mode: 'bm25' | 'semantic' | 'hybrid'
  precision_at_5: number
  mrr_at_5: number
  queries: number
}

export interface EvalQueryRow {
  query_id: string
  query: string
  mode: 'bm25' | 'semantic' | 'hybrid'
  results: string[]
  relevant: boolean[]
  precision_at_5: number
  rr_at_5: number
}

export interface EvaluationReport {
  available: boolean
  message?: string
  created?: string
  conditions?: Record<string, string | number>
  retrieval?: { split: string; rows: EvalModeRow[]; per_query?: EvalQueryRow[] }[]
  skill_gap?: { profiles: number; precision: number; recall: number; f1: number; exact_matches: number; convention: string }
  paths?: { profiles: number; target_coverage: number; unresolved_gaps: number; duplicate_courses: number; prerequisite_violations: number; notes: string[] }
  latency?: { requests: number; median_ms: number; p95_ms: number; cold_start_ms: number | null; machine: string }
  edge_cases?: { name: string; expected: string; observed: string; passed: boolean }[]
  confidence?: {
    labels: number
    queries: number
    base_rate: number
    method: string
    hybrid?: Omit<CalibrationSummary, 'labels' | 'queries' | 'base_rate' | 'method'>
    keyword_only?: Omit<CalibrationSummary, 'labels' | 'queries' | 'base_rate' | 'method'>
  } | null
  findings?: string[]
  limitations?: string[]
}
