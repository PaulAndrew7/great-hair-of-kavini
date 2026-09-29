import { Plus, X } from '@phosphor-icons/react'
import { useId, useState, type FormEvent } from 'react'
import type { CatalogInfo, Difficulty, Filters, Profile, TrackId } from '../types'
import './ProfileBar.css'

interface Props {
  catalog: CatalogInfo | null
  profile: Profile | null
  skills: string[]              // confirmed skills currently shown as chips
  inferred: string[]            // which of those came from the goal text
  onAddSkill: (skill: string) => void
  onRemoveSkill: (skill: string) => void
  track: TrackId | null
  onTrack: (track: TrackId | null) => void
  filters: Filters
  onFilters: (filters: Filters) => void
  disabled: boolean
}

const RATINGS = [4.0, 4.5, 4.7]

export default function ProfileBar(props: Props) {
  const { catalog, profile, skills, inferred, onAddSkill, onRemoveSkill, track, onTrack, filters, onFilters, disabled } = props
  const [draft, setDraft] = useState('')
  const [orgDraft, setOrgDraft] = useState(filters.organization ?? '')
  const ids = { skills: useId(), add: useId(), org: useId(), orgList: useId(), skillList: useId(), diff: useId(), rating: useId() }

  const add = (e: FormEvent) => {
    e.preventDefault()
    const value = draft.trim()
    if (!value) return
    onAddSkill(value)
    setDraft('')
  }

  const commitOrg = () => {
    const value = orgDraft.trim() || null
    if (value !== filters.organization) onFilters({ ...filters, organization: value })
  }

  // Auto shows what it resolved to: a detected curated track, or the track an AI model drafted for this goal.
  const detected = profile?.track_status === 'detected' || profile?.track_status === 'generated' ? profile.track_label : null
  const drafted = profile?.track_status === 'generated'
  const inferredShown = skills.filter((s) => inferred.includes(s))

  return (
    <section className="profile" aria-label="Your profile and filters">
      <div className="profile-skills">
        <h2 className="profile-title" id={ids.skills}>Skills you have</h2>
        <ul className="chips" aria-labelledby={ids.skills}>
          {skills.map((s) => (
            <li key={s} className="chip">
              <span>{s}</span>
              <button type="button" className="chip-x" onClick={() => onRemoveSkill(s)} disabled={disabled}
                aria-label={`Remove ${s} from your skills`}>
                <X size={14} weight="bold" aria-hidden="true" />
              </button>
            </li>
          ))}
          <li>
            <form className="chip-add" onSubmit={add}>
              <label htmlFor={ids.add} className="visually-hidden">Add a skill you have</label>
              <input id={ids.add} className="chip-input" list={ids.skillList} value={draft} disabled={disabled}
                onChange={(e) => setDraft(e.target.value)} placeholder="Add a skill" maxLength={80} autoComplete="off" />
              <button type="submit" className="chip-add-btn" disabled={disabled || !draft.trim()} aria-label="Add skill">
                <Plus size={16} weight="bold" aria-hidden="true" />
              </button>
              <datalist id={ids.skillList}>
                {catalog?.skills.map((s) => <option key={s} value={s} />)}
              </datalist>
            </form>
          </li>
        </ul>
        <p className="profile-note">
          {inferredShown.length > 0
            ? `${inferredShown.join(', ')} ${inferredShown.length === 1 ? 'was' : 'were'} read from your goal. Remove anything that isn't true.`
            : skills.length === 0
              ? 'Skills named in your goal appear here. Add or remove any; your edits win.'
              : 'These count as known when gaps and paths are worked out.'}
        </p>
        {profile?.notes.map((n) => <p key={n} className="profile-note">{n}</p>)}
      </div>

      <fieldset className="profile-track" disabled={disabled}>
        <legend className="profile-title">Track</legend>
        <div className="segmented">
          <label>
            <input type="radio" name="track" checked={track === null} onChange={() => onTrack(null)} />
            <span>Auto{detected && track === null ? (
              // A drafted track's name heads the chart; here it would push the curated tracks onto a second row.
              <span className="seg-detail" title={detected}>: {drafted ? 'AI-drafted' : detected}</span>
            ) : null}</span>
          </label>
          {catalog?.tracks.map((t) => (
            <label key={t.id}>
              <input type="radio" name="track" checked={track === t.id} onChange={() => onTrack(t.id)} />
              <span>{t.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="profile-filters" disabled={disabled}>
        <legend className="profile-title">Filters</legend>
        <div className="filter">
          <label className="field-label" htmlFor={ids.diff}>Difficulty</label>
          <select id={ids.diff} className="select" value={filters.difficulty ?? ''}
            onChange={(e) => onFilters({ ...filters, difficulty: (e.target.value || null) as Difficulty | null })}>
            <option value="">Any level</option>
            <option value="Beginner">Beginner</option>
            <option value="Intermediate">Intermediate</option>
            <option value="Advanced">Advanced</option>
          </select>
        </div>
        <div className="filter filter-org">
          <label className="field-label" htmlFor={ids.org}>Organization</label>
          <input id={ids.org} className="input" list={ids.orgList} value={orgDraft} placeholder="Any organization"
            onChange={(e) => setOrgDraft(e.target.value)} onBlur={commitOrg}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commitOrg() } }} autoComplete="off" />
          <datalist id={ids.orgList}>
            {catalog?.organizations.map((o) => <option key={o.name} value={o.name}>{`${o.count} courses`}</option>)}
          </datalist>
        </div>
        <div className="filter">
          <label className="field-label" htmlFor={ids.rating}>Minimum rating</label>
          <select id={ids.rating} className="select" value={filters.min_rating ?? ''}
            onChange={(e) => onFilters({ ...filters, min_rating: e.target.value ? Number(e.target.value) : null })}>
            <option value="">Any rating</option>
            {RATINGS.map((r) => <option key={r} value={r}>{r.toFixed(1)} and up</option>)}
          </select>
        </div>
      </fieldset>
    </section>
  )
}
