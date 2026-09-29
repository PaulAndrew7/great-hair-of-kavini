import { ArrowRight } from '@phosphor-icons/react'
import type { CSSProperties } from 'react'
import type { CatalogInfo, TrackId } from '../types'
import { EXAMPLES } from './Composer'
import './EmptyState.css'

const EXAMPLE_FOR: Record<TrackId, string> = {
  machine_learning: EXAMPLES[0],
  cloud_computing: EXAMPLES[1],
  data_analytics: EXAMPLES[2],
}

/** Before the first search: teach the chart by showing each track's table, unfilled. */
export default function EmptyState({ catalog, aiTracks, onPick }: {
  catalog: CatalogInfo | null
  aiTracks: boolean
  onPick: (goal: string) => void
}) {
  return (
    <section className="empty" aria-labelledby="empty-title">
      <div className="empty-copy">
        <h2 id="empty-title">Your skill chart appears here</h2>
        <p>
          Prior reads which skills you already have, lays out the rest in learning order, and picks real courses
          from the catalog for each gap. Every course comes with the reasons it was chosen and any concerns.
        </p>
        {aiTracks ? (
          <p>
            With Track on Auto, any goal gets a chart and a path: an AI model drafts the skills for your goal, and
            every course in them still comes from the catalog. The three tracks below are curated by hand; pick one
            to use it as it is.
          </p>
        ) : (
          <p>
            Charts and learning paths cover the three tracks below. Any other goal still gets matching courses.
          </p>
        )}
      </div>
      {catalog && (
        <ul className="empty-tracks">
          {catalog.tracks.map((track) => {
            const skills = catalog.track_skills.filter(
              (s) => track.target_skills.includes(s.skill) || track.supporting_skills.includes(s.skill),
            )
            const periods = [...new Set(skills.map((s) => s.period))].sort((a, b) => a - b)
            const cols = Math.max(...periods.map((p) => skills.filter((s) => s.period === p).length))
            return (
              <li key={track.id} className="empty-track">
                <h3>{track.label}</h3>
                <div className="mini-table" style={{ '--cols': cols } as CSSProperties} aria-hidden="true">
                  {periods.map((p, r) =>
                    skills.filter((s) => s.period === p).map((s, c) => (
                      <span key={s.skill} className="mini-cell" data-kind={track.target_skills.includes(s.skill) ? 'target' : 'supporting'}
                        style={{ gridRow: r + 1, gridColumn: c + 1 }}>{s.abbr}</span>
                    )),
                  )}
                </div>
                <p className="empty-track-skills">{track.target_skills.join(', ')}</p>
                <button type="button" className="btn" onClick={() => onPick(EXAMPLE_FOR[track.id])}>
                  Try an example <ArrowRight size={16} weight="bold" aria-hidden="true" />
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
