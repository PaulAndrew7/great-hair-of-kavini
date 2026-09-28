import { ArrowSquareOut } from '@phosphor-icons/react'
import type { LearningPath as Path, PathStep, SkillTile } from '../types'
import CourseMeta from './CourseMeta'
import './LearningPath.css'

interface Props {
  path: Path
  baseline: Path | null        // set when showing a what-if, for the diff
  tiles: SkillTile[]
  confirmed: string[]
  simulated: string[]
}

function kindOf(skill: string, tiles: SkillTile[]): 'target' | 'supporting' | undefined {
  return tiles.find((t) => t.skill === skill)?.group
}

function buildsOn(step: PathStep, steps: PathStep[], confirmed: string[], simulated: string[]) {
  const p = step.prerequisites
  if (p.status === 'unknown') return 'Prerequisites not verified.'
  if (p.required.length === 0) {
    return p.source === 'course description'
      ? 'No prior skills needed, per the course description.'
      : 'No modelled prerequisites.'
  }
  const parts = p.required.map((skill) => {
    if (confirmed.includes(skill)) return `${skill} (you)`
    if (simulated.includes(skill)) return `${skill} (what-if)`
    const earlier = steps.find((s) => s.step < step.step && s.new_skills.includes(skill))
    return earlier ? `${skill} (step ${earlier.step})` : skill
  })
  const source = p.source === 'course description' ? 'course description' : 'curated guidance'
  return `Builds on ${parts.join(', ')}. Source: ${source}.`
}

export default function LearningPath({ path, baseline, tiles, confirmed, simulated }: Props) {
  const baseIds = baseline ? baseline.steps.map((s) => s.course.course_id) : null
  const ids = path.steps.map((s) => s.course.course_id)
  const dropped = baseline ? baseline.steps.filter((s) => !ids.includes(s.course.course_id)) : []
  const unchanged = baseIds !== null && baseIds.length === ids.length && baseIds.every((id, i) => id === ids[i])

  let summary: string
  if (path.steps.length === 0) summary = path.reason ?? 'No course in the catalog can start this path with the current filters.'
  else {
    const n = path.steps.length
    summary = `${n} ${n === 1 ? 'course' : 'courses'} in dependency order.`
    if (baseline && !unchanged) {
      const swapped = path.steps.filter((s) => !baseIds!.includes(s.course.course_id)).length
      summary += baseline.steps.length !== n
        ? ` Was ${baseline.steps.length} without the what-if.`
        : swapped > 0
          ? ` ${swapped} of ${n} differ from the path without the what-if.`
          : ' Same courses as without the what-if, in a new order.'
    }
  }

  return (
    <section className="path" aria-labelledby="path-title">
      <header className="path-head">
        <h2 id="path-title">Learning path</h2>
        <p className="path-summary">
          {summary}
          {baseline && unchanged && <strong className="path-nochange"> No path change: the same courses in the same order.</strong>}
        </p>
      </header>

      {path.steps.length > 0 && (
        <ol className="steps">
          {path.steps.map((step) => {
            const wasAt = baseIds ? baseIds.indexOf(step.course.course_id) : -1
            const change = baseIds === null ? undefined : wasAt === -1 ? 'added' : wasAt + 1 !== step.step ? 'moved' : undefined
            return (
              <li key={step.course.course_id} className="step" data-change={change}>
                <span className="step-n num" aria-label={`Step ${step.step}`}>{step.step}</span>
                <div className="step-main">
                  {change === 'added' && <p className="step-flag">New in this what-if</p>}
                  {change === 'moved' && <p className="step-flag">Was step {wasAt + 1}</p>}
                  <h3 className="step-title">
                    {step.course.course_url ? (
                      <a href={step.course.course_url} target="_blank" rel="noreferrer">
                        {step.course.title}
                        <ArrowSquareOut size={16} weight="bold" aria-label="(opens course page)" />
                      </a>
                    ) : step.course.title}
                  </h3>
                  <CourseMeta course={step.course} />
                  <p className="step-builds">{buildsOn(step, path.steps, confirmed, simulated)}</p>
                  {step.prerequisites.evidence && (
                    <p className="step-quote">&ldquo;{step.prerequisites.evidence}&rdquo;</p>
                  )}
                  {step.notes.map((n) => <p key={n} className="step-note">{n}</p>)}
                </div>
                <div className="step-adds">
                  <span className="step-adds-label">Adds</span>
                  <span className="step-adds-tiles">
                    {step.new_skills.map((s) => {
                      const t = tiles.find((x) => x.skill === s)
                      return <span key={s} className="mini" data-kind={kindOf(s, tiles)} title={s}>{t?.abbr ?? s}</span>
                    })}
                  </span>
                  <span className="step-adds-names">{step.new_skills.join(', ')}</span>
                </div>
              </li>
            )
          })}
        </ol>
      )}

      {path.steps.length > 0 && (
        <p className="path-foot">Skills listed as added are projected coverage after the course, not proof of mastery.</p>
      )}

      {path.unresolved.length > 0 && (
        <div className="unresolved">
          <h3>Not covered by this path</h3>
          <ul>
            {path.unresolved.map((u) => {
              const t = tiles.find((x) => x.skill === u.skill)
              return (
                <li key={u.skill}>
                  <span className="mini" title={u.skill}>{t?.abbr ?? u.skill}</span>
                  <span><strong>{u.skill}.</strong> {u.reason}</span>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {dropped.length > 0 && (
        <div className="dropped">
          <h3>Dropped in this what-if</h3>
          <ul>
            {dropped.map((s) => (
              <li key={s.course.course_id}><del>{s.course.title}</del> <span className="dropped-was">was step {s.step}</span></li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
