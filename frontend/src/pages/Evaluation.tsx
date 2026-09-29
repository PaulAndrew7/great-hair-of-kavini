import { ArrowClockwise, WarningOctagon } from '@phosphor-icons/react'
import { useCallback, useEffect, useState } from 'react'
import type { ServiceState } from '../App'
import { api, ApiError } from '../api'
import type { EvalQueryRow, EvaluationReport } from '../types'
import './Evaluation.css'

const MODE_LABEL = { bm25: 'Keyword (BM25)', semantic: 'Semantic (MiniLM)', hybrid: 'Hybrid (RRF)' } as const
const fmt = (n: number, d = 2) => n.toFixed(d)

type Load = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ok'; report: EvaluationReport }

export default function Evaluation({ service }: { service: ServiceState }) {
  const [state, setState] = useState<Load>({ kind: 'loading' })

  const load = useCallback(async () => {
    setState({ kind: 'loading' })
    try {
      setState({ kind: 'ok', report: await api.evaluation() })
    } catch (err) {
      setState({ kind: 'error', message: err instanceof ApiError ? err.message : 'Could not read the report.' })
    }
  }, [])

  useEffect(() => {
    if (service.kind !== 'loading') void load()
  }, [service.kind, load])

  return (
    <div className="evaluation">
      <header className="eval-head">
        <h1>Evaluation</h1>
        <p>
          Measured results from the same search engine that serves Discover. This page only reads the saved report;
          it never runs the models.
        </p>
      </header>

      {state.kind === 'loading' && <p className="eval-loading" aria-busy="true">Reading the latest report.</p>}

      {state.kind === 'error' && (
        <section className="notice">
          <WarningOctagon size={28} weight="bold" aria-hidden="true" />
          <div className="notice-body">
            <h2>Report unavailable</h2>
            <p>{state.message}</p>
            <button type="button" className="btn" style={{ justifySelf: 'start' }} onClick={load}>
              <ArrowClockwise size={18} weight="bold" aria-hidden="true" /> Try again
            </button>
          </div>
        </section>
      )}

      {state.kind === 'ok' && !state.report.available && (
        <section className="notice eval-empty">
          <span className="mark" data-state="unknown" aria-hidden="true" style={{ marginTop: 8 }} />
          <div className="notice-body">
            <h2>Not evaluated yet</h2>
            <p>No numbers are shown until a real run exists. Nothing on this page is estimated.</p>
            <p>From the <code>backend</code> folder run <code>.venv\Scripts\python scripts\evaluate.py</code>, then reload this page.</p>
          </div>
        </section>
      )}

      {state.kind === 'ok' && state.report.available && <Report report={state.report} />}
    </div>
  )
}

/** Every labelled query, every method: the per-query evaluation behind the averages above. */
function PerQuery({ blocks }: { blocks: NonNullable<EvaluationReport['retrieval']> }) {
  const rows = new Map<string, { query: string; split: string; modes: Partial<Record<EvalQueryRow['mode'], EvalQueryRow>> }>()
  for (const b of blocks) {
    for (const r of b.per_query ?? []) {
      const entry = rows.get(r.query_id) ?? { query: r.query, split: b.split, modes: {} }
      entry.modes[r.mode] = r
      rows.set(r.query_id, entry)
    }
  }
  if (rows.size === 0) return null
  const cell = (r?: EvalQueryRow) => (r ? <>{fmt(r.precision_at_5)} <span className="eval-rr">/ {fmt(r.rr_at_5)}</span></> : '')
  return (
    <section className="eval-section" aria-labelledby="perq-title">
      <h2 id="perq-title">Every query</h2>
      <p className="eval-note">Precision@5 / reciprocal rank@5 for each labelled query. Run any of these on Discover to see it scored live.</p>
      <div className="eval-scroll">
        <table className="props props-wide">
          <thead>
            <tr><th scope="col">Query</th><th scope="col">Split</th><th scope="col">Keyword</th><th scope="col">Semantic</th><th scope="col">Hybrid</th></tr>
          </thead>
          <tbody>
            {[...rows.entries()].map(([id, e]) => (
              <tr key={id}>
                <th scope="row"><span className="num eval-qid">{id}</span> {e.query}</th>
                <td>{e.split}</td>
                <td className="num">{cell(e.modes.bm25)}</td>
                <td className="num">{cell(e.modes.semantic)}</td>
                <td className="num">{cell(e.modes.hybrid)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Report({ report }: { report: EvaluationReport }) {
  return (
    <div className="eval-body">
      {report.conditions && (
        <dl className="conditions">
          {Object.entries(report.conditions).map(([k, v]) => (
            <div key={k}><dt>{k}</dt><dd className="num">{String(v)}</dd></div>
          ))}
        </dl>
      )}

      {report.retrieval?.map((block) => {
        const best = Math.max(...block.rows.map((r) => r.precision_at_5))
        return (
          <section key={block.split} className="eval-section" aria-labelledby={`ret-${block.split}`}>
            <h2 id={`ret-${block.split}`}>Search relevance, {block.split} queries</h2>
            <table className="props">
              <thead>
                <tr><th scope="col">Method</th><th scope="col">Precision@5</th><th scope="col">MRR@5</th><th scope="col">Queries</th></tr>
              </thead>
              <tbody>
                {block.rows.map((r) => (
                  <tr key={r.mode} data-best={r.precision_at_5 === best || undefined}>
                    <th scope="row">{MODE_LABEL[r.mode]}</th>
                    <td className="num">{fmt(r.precision_at_5)}</td>
                    <td className="num">{fmt(r.mrr_at_5)}</td>
                    <td className="num">{r.queries}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )
      })}

      {report.retrieval && <PerQuery blocks={report.retrieval} />}

      {report.confidence && report.confidence.hybrid && (
        <section className="eval-section" aria-labelledby="conf-title">
          <h2 id="conf-title">Confidence calibration</h2>
          <p className="eval-note">
            Discover shows each course&rsquo;s estimated chance of being relevant. The estimate comes from a model fitted on{' '}
            {report.confidence.labels} labelled results from {report.confidence.queries} queries, and it is scored
            leave-one-query-out, so these numbers come from queries the model did not see.
          </p>
          <table className="props">
            <thead><tr><th scope="col">Mode</th><th scope="col">Brier</th><th scope="col">Base-rate Brier</th><th scope="col">Accuracy</th><th scope="col">AUC</th></tr></thead>
            <tbody>
              {(['hybrid', 'keyword_only'] as const).map((m) => {
                const c = report.confidence?.[m]
                return c ? (
                  <tr key={m}>
                    <th scope="row">{m === 'hybrid' ? 'Hybrid' : 'Keyword only'}</th>
                    <td className="num">{c.brier.toFixed(3)}</td>
                    <td className="num">{c.baseline_brier.toFixed(3)}</td>
                    <td className="num">{fmt(c.accuracy)}</td>
                    <td className="num">{c.auc === null ? 'n/a' : fmt(c.auc)}</td>
                  </tr>
                ) : null
              })}
            </tbody>
          </table>
          <p className="eval-note">{report.confidence.method} Lower Brier is better. An AUC of 0.5 is chance, so the hybrid signal is real but weak.</p>
        </section>
      )}

      <div className="eval-grid">
        {report.skill_gap && (
          <section className="eval-section" aria-labelledby="gap-title">
            <h2 id="gap-title">Skill gaps</h2>
            <table className="props">
              <tbody>
                <tr><th scope="row">Reviewed profiles</th><td className="num">{report.skill_gap.profiles}</td></tr>
                <tr><th scope="row">Precision</th><td className="num">{fmt(report.skill_gap.precision)}</td></tr>
                <tr><th scope="row">Recall</th><td className="num">{fmt(report.skill_gap.recall)}</td></tr>
                <tr><th scope="row">F1</th><td className="num">{fmt(report.skill_gap.f1)}</td></tr>
                <tr><th scope="row">Exact-set matches</th><td className="num">{report.skill_gap.exact_matches} of {report.skill_gap.profiles}</td></tr>
              </tbody>
            </table>
            <p className="eval-note">{report.skill_gap.convention}</p>
          </section>
        )}
        {report.paths && (
          <section className="eval-section" aria-labelledby="path-eval-title">
            <h2 id="path-eval-title">Learning paths</h2>
            <table className="props">
              <tbody>
                <tr><th scope="row">Profiles</th><td className="num">{report.paths.profiles}</td></tr>
                <tr><th scope="row">Mean target coverage</th><td className="num">{fmt(report.paths.target_coverage)}</td></tr>
                <tr><th scope="row">Unresolved gaps</th><td className="num">{report.paths.unresolved_gaps}</td></tr>
                <tr><th scope="row">Duplicate courses</th><td className="num">{report.paths.duplicate_courses}</td></tr>
                <tr><th scope="row">Prerequisite violations</th><td className="num">{report.paths.prerequisite_violations}</td></tr>
              </tbody>
            </table>
            {report.paths.notes.map((n) => <p key={n} className="eval-note">{n}</p>)}
          </section>
        )}
        {report.latency && (
          <section className="eval-section" aria-labelledby="lat-title">
            <h2 id="lat-title">Speed</h2>
            <table className="props">
              <tbody>
                <tr><th scope="row">Warm requests</th><td className="num">{report.latency.requests}</td></tr>
                <tr><th scope="row">Median</th><td className="num">{Math.round(report.latency.median_ms)} ms</td></tr>
                <tr><th scope="row">95th percentile</th><td className="num">{Math.round(report.latency.p95_ms)} ms</td></tr>
                {report.latency.cold_start_ms !== null && (
                  <tr><th scope="row">Cold start</th><td className="num">{(report.latency.cold_start_ms / 1000).toFixed(1)} s</td></tr>
                )}
              </tbody>
            </table>
            <p className="eval-note">{report.latency.machine}</p>
          </section>
        )}
      </div>

      {report.edge_cases && report.edge_cases.length > 0 && (
        <section className="eval-section" aria-labelledby="edge-title">
          <h2 id="edge-title">Edge cases</h2>
          <table className="props props-wide">
            <thead><tr><th scope="col">Case</th><th scope="col">Expected</th><th scope="col">Observed</th><th scope="col">Result</th></tr></thead>
            <tbody>
              {report.edge_cases.map((e) => (
                <tr key={e.name}>
                  <th scope="row">{e.name}</th>
                  <td>{e.expected}</td>
                  <td>{e.observed}</td>
                  <td><span className="result"><span className="mark" data-state={e.passed ? 'known' : 'missing'} aria-hidden="true" />{e.passed ? 'Pass' : 'Fail'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {report.findings && report.findings.length > 0 && (
        <section className="eval-section" aria-labelledby="find-title">
          <h2 id="find-title">What the numbers show</h2>
          <ul className="limits">{report.findings.map((f) => <li key={f}>{f}</li>)}</ul>
        </section>
      )}

      {report.limitations && (
        <section className="eval-section" aria-labelledby="lim-title">
          <h2 id="lim-title">Limitations</h2>
          <ul className="limits">{report.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </section>
      )}
    </div>
  )
}
