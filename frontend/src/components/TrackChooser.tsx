import type { CatalogInfo, Profile, TrackId } from '../types'

/** Shown instead of the chart when the goal is ambiguous or outside the three modelled tracks. */
export default function TrackChooser({ profile, reason, catalog, onPick }: {
  profile: Profile
  reason: string
  catalog: CatalogInfo | null
  onPick: (track: TrackId) => void
}) {
  const ambiguous = profile.track_status === 'ambiguous'
  const options = ambiguous ? profile.track_candidates : (catalog?.tracks.map((t) => t.id) ?? [])
  const label = (id: TrackId) => catalog?.tracks.find((t) => t.id === id)?.label ?? id
  return (
    <section className="notice" data-tone={ambiguous ? 'caution' : undefined} aria-labelledby="chooser-title">
      <span className="mark" data-state={ambiguous ? 'simulated' : 'unknown'} aria-hidden="true" style={{ marginTop: 6 }} />
      <div className="notice-body">
        <h2 id="chooser-title">{ambiguous ? 'Which track did you mean?' : 'No skill chart for this goal'}</h2>
        <p>{reason}</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {options.map((id) => (
            <button key={id} type="button" className="btn" onClick={() => onPick(id)}>
              {ambiguous ? label(id) : `Treat it as ${label(id).toLowerCase()}`}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
