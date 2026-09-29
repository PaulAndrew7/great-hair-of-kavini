import { CaretDown } from '@phosphor-icons/react'
import { useId, useState } from 'react'
import type { QueryEvaluation } from '../types'
import './QueryEval.css'

const f2 = (n: number) => n.toFixed(2)
const pct = (n: number) => `${Math.round(n * 100)}%`
const TRACK_WORD = { certain: 'Certain', high: 'High', medium: 'Medium', low: 'Low', none: 'None', drafted: 'AI-drafted' } as const

interface Tile {
  label: string
  value: string
  sub: string
  kind: 'estimated' | 'measured' | 'checked'
  warn?: boolean
}

/**
 * The per-query report card. Three kinds of number are labelled apart so none is passed off as another:
 * estimated (calibrated model), measured (human labels, only for frozen evaluation queries), checked (rules).
 */
export default function QueryEval({ evaluation: ev, mode }: { evaluation: QueryEvaluation; mode: 'hybrid' | 'keyword_only' }) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const r = ev.retrieval
  const cal = ev.calibration
  const tiles: Tile[] = []

  if (r.expected_precision !== null && r.expected_relevant !== null) {
    tiles.push({
      label: 'Estimated precision@' + r.k,
      value: f2(r.expected_precision),
      sub: `about ${r.expected_relevant.toFixed(1)} of ${r.k} likely relevant${r.extrapolated ? '; outside the labelled subjects' : ''}`,
      kind: 'estimated',
      warn: r.extrapolated,
    })
  }
  if (ev.ground_truth) {
    const g = ev.ground_truth
    tiles.push({
      label: 'Measured precision@' + r.k,
      value: f2(g.precision_at_k),
      sub: `${g.relevant} of ${g.shown} labelled relevant, RR ${f2(g.rr_at_k)} (${g.split} query ${g.query_id})`,
      kind: 'measured',
    })
  } else {
    tiles.push({ label: 'Measured precision', value: 'No labels', sub: 'not one of the 18 labelled queries', kind: 'measured' })
  }
  if (r.channel_agreement !== null) {
    tiles.push({
      label: 'Channel agreement',
      value: `${Math.round(r.channel_agreement * r.agreement_depth)} of ${r.agreement_depth}`,
      sub: 'courses in both the keyword and the semantic top 10',
      kind: 'checked',
    })
  }
  tiles.push({
    label: ev.track.confidence === 'drafted' ? 'Track' : 'Track detection',
    value: TRACK_WORD[ev.track.confidence],
    sub: ev.track.explanation,
    kind: 'checked',
    // A drafted track is unreviewed: flagged like other cautions, with the reason in the sub-line.
    warn: ev.track.confidence === 'low' || ev.track.confidence === 'drafted',
  })
  if (ev.path) {
    const p = ev.path
    tiles.push({
      label: 'Path check',
      value: p.target_coverage_projected !== null ? pct(p.target_coverage_projected) : `${p.steps} steps`,
      sub: `goal skills covered after the path; ${p.prerequisite_violations} prerequisite violation${p.prerequisite_violations === 1 ? '' : 's'}, ${p.duplicates} duplicate${p.duplicates === 1 ? '' : 's'}`,
      kind: 'checked',
      warn: p.prerequisite_violations > 0 || p.duplicates > 0,
    })
  }
  if (ev.skill_gap) {
    const g = ev.skill_gap
    tiles.push({
      label: 'Skill gap F1',
      value: f2(g.f1),
      sub: `against labelled profile ${g.profile_id}${g.exact ? ', exact match' : ''}`,
      kind: 'measured',
      warn: !g.exact,
    })
  }

  return (
    <section className="qe" aria-labelledby="qe-title">
      <header className="qe-head">
        <h2 id="qe-title">Answer check</h2>
        <p className="qe-sub">
          Evaluated for this query. <span className="qe-key" data-kind="estimated">Estimated</span> comes from a model calibrated
          on labelled results; <span className="qe-key" data-kind="measured">measured</span> needs human labels;{' '}
          <span className="qe-key" data-kind="checked">checked</span> is a rule test.
        </p>
      </header>
      <ul className="qe-tiles">
        {tiles.map((t) => (
          <li key={t.label} className="qe-tile" data-kind={t.kind} data-warn={t.warn || undefined}>
            <span className="qe-label">{t.label}</span>
            <span className="qe-value num">{t.value}</span>
            <span className="qe-tile-sub">{t.sub}</span>
          </li>
        ))}
      </ul>
      {ev.notes.map((n) => <p key={n} className="qe-note">{n}</p>)}

      <button type="button" className="disclose" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>
        How these numbers are made
        <CaretDown size={16} weight="bold" aria-hidden="true" />
      </button>
      <div id={panelId} className="qe-details" hidden={!open}>
        <section>
          <h3>Confidence model</h3>
          {cal ? (
            <>
              <p>
                Each course&rsquo;s confidence is a {mode === 'hybrid' ? 'logistic model over semantic similarity, semantic rank and channel agreement' : 'constant: keyword-only mode has no signal that beat the base rate'},
                fitted on <span className="num">{cal.labels}</span> labelled results from <span className="num">{cal.queries}</span> queries.
                Scored leave-one-query-out, so every number below comes from queries the model did not see.
              </p>
              <table className="props">
                <tbody>
                  <tr><th scope="row">Brier score (lower is better)</th><td className="num">{cal.brier.toFixed(3)}</td></tr>
                  <tr><th scope="row">Brier, always guessing the base rate</th><td className="num">{cal.baseline_brier.toFixed(3)}</td></tr>
                  <tr><th scope="row">Accuracy at 50%</th><td className="num">{pct(cal.accuracy)}</td></tr>
                  <tr><th scope="row">AUC (0.5 is chance)</th><td className="num">{cal.auc === null ? 'n/a' : f2(cal.auc)}</td></tr>
                  <tr><th scope="row">Relevant among labelled results</th><td className="num">{pct(cal.base_rate)}</td></tr>
                </tbody>
              </table>
              <table className="props">
                <caption className="qe-caption">Does a stated confidence come true? (held-out)</caption>
                <thead><tr><th scope="col">Confidence band</th><th scope="col">Results</th><th scope="col">Mean stated</th><th scope="col">Actually relevant</th></tr></thead>
                <tbody>
                  {cal.reliability.map((b) => (
                    <tr key={b.lo}>
                      <th scope="row" className="num">{pct(b.lo)}&ndash;{pct(b.hi)}</th>
                      <td className="num">{b.n}</td>
                      <td className="num">{pct(b.predicted)}</td>
                      <td className="num">{pct(b.observed)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="qe-note">
                The signal is weak: it separates relevant from irrelevant top results only modestly (AUC above), because
                almost every top result is already on topic. Treat a confidence as a rough prior, not a verdict.
              </p>
            </>
          ) : <p>No calibration file yet. Run <code>scripts/evaluate.py</code> to enable confidence estimates.</p>}
        </section>
        {ev.reference && (
          <section>
            <h3>Whole-system reference</h3>
            <table className="props">
              <tbody>
                {ev.reference.precision_at_5 !== null && (
                  <tr><th scope="row">{ev.reference.mode === 'hybrid' ? 'Hybrid' : 'Keyword'} precision@5, {ev.reference.queries} held-out queries</th><td className="num">{f2(ev.reference.precision_at_5)}</td></tr>
                )}
                {ev.reference.mrr_at_5 !== null && <tr><th scope="row">MRR@5, same queries</th><td className="num">{f2(ev.reference.mrr_at_5)}</td></tr>}
                {ev.reference.gap_f1 !== null && <tr><th scope="row">Skill-gap F1, {ev.reference.gap_profiles} profiles</th><td className="num">{f2(ev.reference.gap_f1)}</td></tr>}
                {ev.reference.path_target_coverage !== null && <tr><th scope="row">Path target coverage</th><td className="num">{pct(ev.reference.path_target_coverage)}</td></tr>}
              </tbody>
            </table>
            <p className="qe-note">From the saved evaluation report; see the Evaluation page for every query.</p>
          </section>
        )}
        <section>
          <h3>This query</h3>
          <table className="props">
            <tbody>
              <tr><th scope="row">Search terms</th><td>{r.query_terms.join(', ') || 'none'}</td></tr>
              <tr><th scope="row">Terms no shown course contains</th><td>{r.unmatched_terms.join(', ') || 'none'}</td></tr>
              {r.top_confidence !== null && r.min_confidence !== null && (
                <tr><th scope="row">Confidence range of shown courses</th><td className="num">{pct(r.min_confidence)}&ndash;{pct(r.top_confidence)}</td></tr>
              )}
              {Object.keys(ev.track.scores).length > 0 && (
                <tr><th scope="row">Track cues found</th><td>{Object.entries(ev.track.scores).map(([k, v]) => `${k} ${v}`).join(', ')}</td></tr>
              )}
              {ev.path && ev.path.mean_skill_similarity !== null && (
                <tr><th scope="row">Mean path skill similarity</th><td className="num">{f2(ev.path.mean_skill_similarity)}</td></tr>
              )}
              {ev.path && <tr><th scope="row">Path steps with unverified prerequisites</th><td className="num">{ev.path.unverified_steps}</td></tr>}
              {ev.ground_truth && <tr><th scope="row">Labels</th><td>{ev.ground_truth.note}</td></tr>}
              {ev.skill_gap && (ev.skill_gap.false_positives.length > 0 || ev.skill_gap.false_negatives.length > 0) && (
                <tr><th scope="row">Gap errors</th><td>
                  {ev.skill_gap.false_positives.length > 0 && `Wrongly missing: ${ev.skill_gap.false_positives.join(', ')}. `}
                  {ev.skill_gap.false_negatives.length > 0 && `Missed: ${ev.skill_gap.false_negatives.join(', ')}.`}
                </td></tr>
              )}
            </tbody>
          </table>
          {ev.path && ev.path.violations.length > 0 && <ul className="limits">{ev.path.violations.map((v) => <li key={v}>{v}</li>)}</ul>}
        </section>
      </div>
    </section>
  )
}
