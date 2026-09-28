import { useCallback, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import type { RecommendRequest, RecommendResponse } from '../types'

type Status = 'idle' | 'loading' | 'ready' | 'error'

interface Channel {
  ctl: AbortController | null
  seq: number
}

function start(ch: Channel): { signal: AbortSignal; seq: number } {
  ch.ctl?.abort()
  ch.ctl = new AbortController()
  ch.seq += 1
  return { signal: ch.ctl.signal, seq: ch.seq }
}

function message(err: unknown): string {
  if (err instanceof ApiError) {
    return err.problems.length ? err.problems.map((p) => p.message).join(' ') : err.message
  }
  return 'Something went wrong while fetching recommendations.'
}

/**
 * Baseline and What-If run through the same /recommend call but live in separate slots:
 * the baseline is never overwritten by a simulation, and only the newest response in each
 * slot is applied (older in-flight requests are aborted and ignored).
 */
export function useRecommend() {
  const [baseline, setBaseline] = useState<RecommendResponse | null>(null)
  const [simulation, setSimulation] = useState<RecommendResponse | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [simBusy, setSimBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [simError, setSimError] = useState<string | null>(null)
  const base = useRef<Channel>({ ctl: null, seq: 0 })
  const sim = useRef<Channel>({ ctl: null, seq: 0 })

  const clearSimulation = useCallback(() => {
    sim.current.ctl?.abort()
    sim.current.seq += 1
    setSimulation(null)
    setSimBusy(false)
    setSimError(null)
  }, [])

  const simulate = useCallback(async (req: RecommendRequest) => {
    if (req.simulated_skills.length === 0) {
      clearSimulation()
      return
    }
    const { signal, seq } = start(sim.current)
    setSimBusy(true)
    setSimError(null)
    try {
      const res = await api.recommend(req, signal)
      if (seq !== sim.current.seq) return
      setSimulation(res)
    } catch (err) {
      if ((err as Error).name === 'AbortError' || seq !== sim.current.seq) return
      setSimError(message(err))
    } finally {
      if (seq === sim.current.seq) setSimBusy(false)
    }
  }, [clearSimulation])

  const load = useCallback(async (req: RecommendRequest) => {
    const { signal, seq } = start(base.current)
    setStatus('loading')
    setError(null)
    try {
      const res = await api.recommend({ ...req, simulated_skills: [] }, signal)
      if (seq !== base.current.seq) return
      setBaseline(res)
      setStatus('ready')
    } catch (err) {
      if ((err as Error).name === 'AbortError' || seq !== base.current.seq) return
      setError(message(err))
      setStatus('error')
      return
    }
    if (req.simulated_skills.length) void simulate(req)
    else clearSimulation()
  }, [simulate, clearSimulation])

  return { baseline, simulation, status, simBusy, error, simError, load, simulate, clearSimulation }
}
