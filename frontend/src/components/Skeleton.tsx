import './Skeleton.css'

/** Loading placeholder shaped like the result: a list of courses beside a path over a chart of tiles. */
export default function Skeleton() {
  const rows = [4, 2, 1]
  return (
    <div className="results skeleton" aria-busy="true" aria-label="Loading recommendations">
      <div className="results-side">
        <span className="sk-line" style={{ width: '16rem', height: 32 }} />
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="sk-course">
            <span className="sk-line" style={{ width: '90%' }} />
            <span className="sk-line" style={{ width: '60%' }} />
          </div>
        ))}
      </div>
      <div className="results-main">
        <span className="sk-line" style={{ width: '12rem', height: 32 }} />
        {Array.from({ length: 3 }, (_, i) => <span key={i} className="sk-line" style={{ width: `${80 - i * 12}%` }} />)}
        <span className="sk-line" style={{ width: '14rem', height: 40, marginTop: 48 }} />
        <div className="sk-table">
          {rows.map((n, r) => (
            <div key={r} className="sk-row">
              {Array.from({ length: n }, (_, i) => <span key={i} className="sk-tile" />)}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
