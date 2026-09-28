import { ArrowClockwise, WarningOctagon } from '@phosphor-icons/react'
import { useEffect, useMemo, useState } from 'react'
import type { ServiceState } from '../App'
import { api } from '../api'
import Composer from '../components/Composer'
import CourseList from '../components/CourseList'
import EmptyState from '../components/EmptyState'
import LearningPath from '../components/LearningPath'
import ProfileBar from '../components/ProfileBar'
import SkillChart from '../components/SkillChart'
import Skeleton from '../components/Skeleton'
import TrackChooser from '../components/TrackChooser'
import WhatIfBar from '../components/WhatIfBar'
import { useRecommend } from '../hooks/useRecommend'
import type { FeedbackLabel, Filters, Recommendation, RecommendRequest, TrackId } from '../types'
import './Discover.css'

const NO_FILTERS: Filters = { difficulty: null, organization: null, min_rating: null }
const same = (a: string, b: string) => a.toLocaleLowerCase() === b.toLocaleLowerCase()

interface Draft {
  goal: string
  track: TrackId | null
  added: string[]
  excluded: string[]
  filters: Filters
  simulated: string[]
}

export default function Discover({ service, onRetry }: { service: ServiceState; onRetry: () => void }) {
  const catalog = service.kind === 'ready' ? service.catalog : null
  const ready = service.kind === 'ready'
  const [goal, setGoal] = useState('')
  const [draft, setDraft] = useState<Draft>({ goal: '', track: null, added: [], excluded: [], filters: NO_FILTERS, simulated: [] })
  const rec = useRecommend()
  const { baseline, simulation } = rec

  const request = (d: Draft): RecommendRequest => ({
    goal: d.goal,
    goal_track: d.track,
    known_skills: d.added,
    excluded_skills: d.excluded,
    simulated_skills: d.simulated,
    filters: d.filters,
    top_k: 5,
  })

  /** Apply a change to the working profile and re-run the baseline (and any active what-if). */
  const rerun = (patch: Partial<Draft>) => {
    const next = { ...draft, ...patch }
    setDraft(next)
    if (next.goal) void rec.load(request(next))
  }

  const submit = (text: string, fresh = false) => {
    const changed = !same(text, draft.goal)
    rerun({
      goal: text,
      track: changed || fresh ? null : draft.track,
      excluded: changed || fresh ? [] : draft.excluded,
      added: fresh ? [] : draft.added,
      simulated: [],
    })
  }

  // Keep explicit skills in the backend's canonical spelling so chips and removals line up.
  useEffect(() => {
    if (!baseline) return
    const p = baseline.profile
    const explicit = p.confirmed_skills.filter((s) => !p.inferred_skills.includes(s))
    setDraft((d) => (d.added.join('|') === explicit.join('|') ? d : { ...d, added: explicit }))
  }, [baseline])

  const addSkill = (skill: string) => {
    if (draft.added.some((s) => same(s, skill))) return
    rerun({ added: [...draft.added, skill], excluded: draft.excluded.filter((s) => !same(s, skill)) })
  }
  const removeSkill = (skill: string) => {
    const inferred = baseline?.profile.inferred_skills.some((s) => same(s, skill))
    rerun({
      added: draft.added.filter((s) => !same(s, skill)),
      excluded: inferred ? [...draft.excluded, skill] : draft.excluded,
      simulated: draft.simulated.filter((s) => !same(s, skill)),
    })
  }

  const toggleSimulated = (skill: string) => {
    const simulated = draft.simulated.includes(skill) ? draft.simulated.filter((s) => s !== skill) : [...draft.simulated, skill]
    const next = { ...draft, simulated }
    setDraft(next)
    void rec.simulate(request(next))
  }
  const resetSimulation = () => {
    setDraft((d) => ({ ...d, simulated: [] }))
    rec.clearSimulation()
  }

  const shown = draft.simulated.length > 0 && simulation ? simulation : baseline
  const comparing = draft.simulated.length > 0 && simulation && baseline ? baseline : null

  const sendFeedback = async (course: Recommendation, label: FeedbackLabel, comment?: string) => {
    if (!shown) return
    await api.feedback({
      course_id: course.course_id,
      label,
      comment,
      request_id: shown.request_id,
      goal: shown.profile.goal,
      goal_track: shown.profile.track_id,
      known_skills: shown.profile.confirmed_skills,
      simulated_skills: shown.profile.simulated_skills,
      is_simulation: shown.is_simulation,
    })
  }

  const chips = baseline ? baseline.profile.confirmed_skills : draft.added
  const unresolved = useMemo(() => shown?.learning_path.unresolved.map((u) => u.skill) ?? [], [shown])
  const courseWarning = shown?.warnings.find((w) => ['filters_excluded', 'no_matches', 'few_matches'].includes(w.code))
  const degraded = shown?.warnings.find((w) => w.code === 'keyword_only')

  if (service.kind === 'down') {
    return (
      <div className="discover">
        <section className="notice offline" aria-labelledby="offline-title">
          <WarningOctagon size={28} weight="bold" aria-hidden="true" />
          <div className="notice-body">
            <h2 id="offline-title">The course service is not running</h2>
            <p>{service.message}</p>
            <p>From the <code>backend</code> folder run <code>.venv\Scripts\python -m uvicorn app.main:app --port 8100</code>, then retry.</p>
            <button type="button" className="btn" onClick={onRetry} style={{ justifySelf: 'start' }}>
              <ArrowClockwise size={18} weight="bold" aria-hidden="true" /> Retry connection
            </button>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="discover">
      <Composer
        goal={goal}
        onGoalChange={setGoal}
        onSubmit={(text) => submit(text, !baseline || !same(text, draft.goal))}
        busy={rec.status === 'loading'}
        disabled={!ready}
        error={rec.status === 'error' ? rec.error : null}
      />
      <ProfileBar
        catalog={catalog}
        profile={baseline?.profile ?? null}
        skills={chips}
        inferred={baseline?.profile.inferred_skills ?? []}
        onAddSkill={addSkill}
        onRemoveSkill={removeSkill}
        track={draft.track}
        onTrack={(track) => rerun({ track, simulated: [] })}
        filters={draft.filters}
        onFilters={(filters) => rerun({ filters })}
        disabled={!ready}
      />

      {rec.status === 'error' && baseline && (
        <div className="inline-error" role="alert">
          <WarningOctagon size={20} weight="bold" aria-hidden="true" />
          <span>{rec.error} Showing the previous result.</span>
          <button type="button" className="btn-quiet btn" onClick={() => rerun({})}>Try again</button>
        </div>
      )}

      {!baseline && rec.status === 'idle' && <EmptyState catalog={catalog} onPick={(g) => { setGoal(g); submit(g, true) }} />}
      {!baseline && rec.status === 'loading' && <Skeleton />}
      {!baseline && rec.status === 'error' && (
        <section className="notice" style={{ marginTop: 32 }}>
          <WarningOctagon size={28} weight="bold" aria-hidden="true" />
          <div className="notice-body">
            <h2>Could not get recommendations</h2>
            <p>{rec.error}</p>
            <button type="button" className="btn" style={{ justifySelf: 'start' }} onClick={() => rerun({})}>Try again</button>
          </div>
        </section>
      )}

      {baseline && shown && (
        <>
          {degraded && <p className="degraded" role="status"><span className="mark" data-state="simulated" aria-hidden="true" />{degraded.message}</p>}
          {draft.simulated.length > 0 && (
            <WhatIfBar simulated={draft.simulated} baseline={baseline} simulation={simulation} busy={rec.simBusy}
              error={rec.simError} onRemove={toggleSimulated} onReset={resetSimulation} />
          )}
          {/* Courses on the left, skill chart and path on the right; DOM order matches so tab order reads left to right. */}
          <div className="results" aria-busy={rec.status === 'loading'} data-stale={rec.status === 'loading' || undefined}>
            <div className="results-side">
              <CourseList
                courses={shown.courses}
                baselineIds={comparing ? comparing.courses.map((c) => c.course_id) : null}
                tiles={shown.skill_gap.tiles}
                effective={shown.profile.effective_skills}
                searchText={shown.profile.search_text}
                eligibleCount={shown.eligible_count}
                onFeedback={sendFeedback}
              />
              {courseWarning && (
                <div className="notice course-warning" data-tone={courseWarning.code === 'few_matches' ? undefined : 'caution'}>
                  <span className="mark" data-state="unknown" aria-hidden="true" style={{ marginTop: 6 }} />
                  <div className="notice-body">
                    <p>{courseWarning.message}</p>
                    {courseWarning.code === 'filters_excluded' && (
                      <button type="button" className="btn" style={{ justifySelf: 'start' }} onClick={() => rerun({ filters: NO_FILTERS })}>
                        Clear filters
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
            <div className="results-main">
              {shown.skill_gap.available && shown.profile.track_label ? (
                <SkillChart
                  gap={shown.skill_gap}
                  trackLabel={shown.profile.track_label}
                  simulated={draft.simulated}
                  unresolved={unresolved}
                  onToggle={toggleSimulated}
                  revealKey={baseline.request_id}
                  busy={rec.simBusy}
                />
              ) : (
                <TrackChooser profile={shown.profile} reason={shown.skill_gap.reason ?? ''} catalog={catalog}
                  onPick={(track) => rerun({ track, simulated: [] })} />
              )}
              {shown.learning_path.available && (
                <LearningPath
                  path={shown.learning_path}
                  baseline={comparing?.learning_path ?? null}
                  tiles={shown.skill_gap.tiles}
                  confirmed={shown.profile.confirmed_skills}
                  simulated={shown.profile.simulated_skills}
                />
              )}
            </div>
          </div>
          <p className="provenance">
            Catalog <span className="num">{shown.data_version}</span>, rules {shown.rules_version},{' '}
            {shown.mode === 'hybrid' ? 'hybrid retrieval' : 'keyword retrieval'}, answered in <span className="num">{Math.round(shown.timing_ms)}</span> ms.
          </p>
        </>
      )}
    </div>
  )
}
