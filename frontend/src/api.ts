import type {
  CatalogInfo, EvaluationReport, FeedbackLabel, Health, RecommendRequest, RecommendResponse, TrackId,
} from './types'

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

export class ApiError extends Error {
  status: number
  problems: { field: string; message: string }[]
  constructor(status: number, message: string, problems: { field: string; message: string }[] = []) {
    super(message)
    this.status = status
    this.problems = problems
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err
    throw new ApiError(0, 'The course service is not reachable. Start the backend on port 8100, then retry.')
  }
  if (!res.ok) {
    let message = `The service answered ${res.status}.`
    let problems: { field: string; message: string }[] = []
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      if (Array.isArray(body.problems)) problems = body.problems
    } catch {
      /* non-JSON error body: keep the status message */
    }
    if (res.status === 502 || res.status === 504) {
      message = 'The course service is not reachable. Start the backend on port 8100, then retry.'
    }
    throw new ApiError(res.status, message, problems)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/health'),
  catalog: () => request<CatalogInfo>('/catalog'),
  evaluation: () => request<EvaluationReport>('/evaluation'),
  recommend: (body: RecommendRequest, signal?: AbortSignal) =>
    request<RecommendResponse>('/recommend', { method: 'POST', body: JSON.stringify(body), signal }),
  feedback: (body: {
    course_id: string
    label: FeedbackLabel
    request_id: string
    comment?: string
    goal: string
    goal_track: TrackId | null
    known_skills: string[]
    simulated_skills: string[]
    is_simulation: boolean
  }) => request<{ feedback_id: number; stored_at: string }>('/feedback', { method: 'POST', body: JSON.stringify(body) }),
}
