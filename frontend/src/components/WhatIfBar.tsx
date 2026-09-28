import { ArrowCounterClockwise } from '@phosphor-icons/react'
import type { RecommendResponse } from '../types'
import './WhatIfBar.css'

interface Props {
  simulated: string[]
  baseline: RecommendResponse
  simulation: RecommendResponse | null
  busy: boolean
  error: string | null
  onRemove: (skill: string) => void
  onReset: () => void
}

function missingCount(r: RecommendResponse): number {
  return r.skill_gap.available ? r.skill_gap.missing_targets.length + r.skill_gap.missing_supporting.length : 0
}

export default function WhatIfBar({ simulated, baseline, simulation, busy, error, onRemove, onReset }: Props) {
  let delta: string | null = null
  if (simulation && !busy) {
    const gapBefore = missingCount(baseline)
    const gapAfter = missingCount(simulation)
    const before = baseline.learning_path.steps.map((s) => s.course.course_id)
    const after = simulation.learning_path.steps.map((s) => s.course.course_id)
    const samePath = before.length === after.length && before.every((id, i) => id === after[i])
    const swapped = after.filter((id) => !before.includes(id)).length
    const courses = (n: number) => `${n} ${n === 1 ? 'course' : 'courses'}`
    let path: string
    if (samePath) path = 'No path change.'
    else if (before.length !== after.length) path = `Path: ${courses(before.length)} to ${courses(after.length)}.`
    else if (swapped > 0) path = `Path: still ${courses(after.length)}, ${swapped} swapped.`
    else path = `Path: same ${courses(after.length)}, new order.`
    delta = `Skills to get: ${gapBefore} to ${gapAfter}. ${path}`
  }

  return (
    <div className="whatif" role="region" aria-label="What-if simulation">
      <div className="whatif-main">
        <p className="whatif-title">What-if</p>
        <p className="whatif-text">
          Treating
          {simulated.map((s) => (
            <button key={s} type="button" className="whatif-skill" onClick={() => onRemove(s)} aria-label={`Stop treating ${s} as known`}>
              {s}
            </button>
          ))}
          as known. Your saved profile is unchanged.
        </p>
        <p className="whatif-delta" role="status">
          {busy ? 'Recalculating.' : error ? `Could not recalculate: ${error}` : delta}
        </p>
      </div>
      <button type="button" className="btn whatif-reset" onClick={onReset}>
        <ArrowCounterClockwise size={18} weight="bold" aria-hidden="true" />
        Reset simulation
      </button>
    </div>
  )
}
