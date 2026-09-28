import { useMemo, useState, type CSSProperties } from 'react'
import type { SkillGap, SkillTile } from '../types'
import './SkillChart.css'

interface Props {
  gap: SkillGap
  trackLabel: string
  simulated: string[]
  unresolved: string[]
  onToggle: (skill: string) => void
  revealKey: string
  busy: boolean
}

const KEY_COLS = 2
const KEY_ROWS = 2

/** Rows by period (learning order); the key goes into the empty notch the staircase leaves. */
function layout(tiles: SkillTile[]) {
  const periods = [...new Set(tiles.map((t) => t.period))].sort((a, b) => a - b)
  const rows = periods.map((p) => tiles.filter((t) => t.period === p))
  const cols = Math.max(...rows.map((r) => r.length))
  let notch: { row: number; col: number } | null = null
  if (cols >= KEY_COLS + 1) {
    for (let start = 0; start + KEY_ROWS <= rows.length && !notch; start++) {
      const fits = rows.slice(start, start + KEY_ROWS).every((r) => cols - r.length >= KEY_COLS)
      if (fits) notch = { row: start, col: cols - KEY_COLS }
    }
  }
  return { periods, rows, cols, notch }
}

function stateLabel(tile: SkillTile): string {
  if (tile.state === 'known') return 'you have it'
  if (tile.state === 'simulated') return 'what-if: treated as known'
  return tile.group === 'target' ? 'goal skill, missing' : 'foundation, missing'
}

function Key() {
  return (
    <div className="chart-key">
      <h3>Key</h3>
      <ul>
        <li><span className="key-swatch" data-kind="known" /> You have it</li>
        <li><span className="key-swatch" data-kind="target" /> Goal skill to get</li>
        <li><span className="key-swatch" data-kind="supporting" /> Foundation to get</li>
        <li><span className="key-swatch" data-kind="simulated" /> What-if</li>
      </ul>
      <p>Rows run in learning order. Press a blue or yellow tile to see what changes if you knew it.</p>
    </div>
  )
}

export default function SkillChart({ gap, trackLabel, simulated, unresolved, onToggle, revealKey, busy }: Props) {
  const [active, setActive] = useState<string | null>(null)
  // Optimistic: a pressed tile shows its what-if state before the recalculated response lands.
  const tiles = useMemo(
    () => gap.tiles.map((t): SkillTile => {
      if (t.state === 'known') return t
      if (simulated.includes(t.skill)) return { ...t, state: 'simulated' }
      return t.state === 'simulated' ? { ...t, state: 'missing', path_step: null } : t
    }),
    [gap.tiles, simulated],
  )
  const { periods, rows, cols, notch } = useMemo(() => layout(tiles), [tiles])
  const bySkill = useMemo(() => new Map(tiles.map((t) => [t.skill, t])), [tiles])
  const activeTile = active ? bySkill.get(active) ?? null : null
  const related = new Set(activeTile?.requires ?? [])
  const coverage = gap.coverage

  const readout = activeTile ? (
    <>
      <strong>{activeTile.skill}</strong>
      {activeTile.requires.length > 0
        ? <> builds on {activeTile.requires.join(', ')}. {activeTile.reason} <span className="readout-src">(curated guidance)</span></>
        : <> has no modelled prerequisite in this track.</>}
      {' '}<span className="num">{activeTile.course_count}</span> catalog courses list it.
      {activeTile.path_step ? <> Your path covers it in step {activeTile.path_step}.</> : null}
      {unresolved.includes(activeTile.skill) ? <> No course in the path covers it yet.</> : null}
    </>
  ) : (
    <>Point at or focus a tile to see what it builds on.</>
  )

  return (
    <section className="chart" aria-labelledby="chart-title" aria-busy={busy}>
      <header className="chart-head">
        <h2 id="chart-title">{trackLabel}</h2>
        {coverage && (
          <div className="coverage" role="group" aria-label={`Goal skills: ${coverage.covered_now} of ${coverage.total} now, ${coverage.projected} of ${coverage.total} after the path`}>
            <div className="coverage-row">
              <span className="coverage-label">Now</span>
              <span className="coverage-squares" aria-hidden="true">
                {gap.target_skills.map((s) => {
                  const t = bySkill.get(s)!
                  return <span key={s} className="csq" data-on={t.state !== 'missing' ? t.state : undefined}>{t.abbr}</span>
                })}
              </span>
              <span className="coverage-count num">{coverage.covered_now} of {coverage.total}</span>
            </div>
            <div className="coverage-row">
              <span className="coverage-label">After path</span>
              <span className="coverage-squares" aria-hidden="true">
                {gap.target_skills.map((s) => {
                  const t = bySkill.get(s)!
                  const on = t.state !== 'missing' ? t.state : t.path_step ? 'projected' : undefined
                  return <span key={s} className="csq" data-on={on}>{t.abbr}</span>
                })}
              </span>
              <span className="coverage-count num">{coverage.projected} of {coverage.total}</span>
            </div>
            <p className="coverage-note">Counts catalog coverage, not mastery.</p>
          </div>
        )}
      </header>

      <div
        key={revealKey}
        className="table"
        style={{ '--cols': cols } as CSSProperties}
        onMouseLeave={() => setActive(null)}
      >
        {periods.map((p, r) => (
          <span key={`p${p}`} className="period" style={{ gridRow: r + 1 }} aria-hidden="true">{p}</span>
        ))}
        {rows.map((row, r) =>
          row.map((tile, c) => {
            const toggleable = tile.state !== 'known'
            const isSim = simulated.includes(tile.skill)
            const dim = activeTile && tile.skill !== activeTile.skill && !related.has(tile.skill)
            const style = { gridRow: r + 1, gridColumn: c + 2, '--i': r * 3 + c } as CSSProperties
            return (
              <button
                key={tile.skill}
                type="button"
                className="tile"
                data-state={tile.state}
                data-group={tile.group}
                data-related={related.has(tile.skill) ? 'required' : undefined}
                data-dim={dim ? 'true' : undefined}
                style={style}
                aria-pressed={toggleable ? isSim : undefined}
                aria-disabled={!toggleable || undefined}
                aria-label={`${tile.skill}, ${stateLabel(tile)}${tile.path_step ? `, covered in path step ${tile.path_step}` : ''}, ${tile.course_count} catalog courses.${toggleable ? ' Press to toggle what-if.' : ''}`}
                onClick={() => toggleable && onToggle(tile.skill)}
                onMouseEnter={() => setActive(tile.skill)}
                onFocus={() => setActive(tile.skill)}
                onBlur={() => setActive(null)}
              >
                <span className="tile-top">
                  <span className="tile-step">
                    {tile.state === 'simulated' ? 'What-if' : tile.path_step ? `Step ${tile.path_step}` : unresolved.includes(tile.skill) ? 'No course' : ''}
                  </span>
                  <span className="mark" data-state={tile.state} aria-hidden="true" />
                </span>
                <span className="tile-sym">{tile.abbr}</span>
                <span className="tile-name">{tile.skill}</span>
                <span className="tile-count num">{tile.course_count} courses</span>
              </button>
            )
          }),
        )}
        {notch && (
          <div className="chart-key-slot" style={{ gridRow: `${notch.row + 1} / span ${KEY_ROWS}`, gridColumn: `${notch.col + 2} / span ${KEY_COLS}` }}>
            <Key />
          </div>
        )}
      </div>
      {!notch && <div className="chart-key-below"><Key /></div>}
      <p className="readout" aria-live="polite">{readout}</p>
    </section>
  )
}
