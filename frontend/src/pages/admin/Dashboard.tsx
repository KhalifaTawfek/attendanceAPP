import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmt, type Stats } from '../../api'
import { ErrorNote } from '../../components'

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Stats>('/admin/stats').then(setStats).catch((e) => setError(e.message))
  }, [])

  if (!stats) return error ? <ErrorNote error={error} /> : <p className="muted">Loading…</p>

  const tiles: [string, number, string?][] = [
    ['Enrolled users', stats.total_users, '/admin/users'],
    ['Events', stats.total_events, '/admin/events'],
    ['Upcoming events', stats.upcoming_events, '/admin/events'],
    ['Submissions', stats.total_attendances, '/admin/attendances'],
    ['Pending review', stats.pending, '/admin/attendances?status=pending'],
    ['Approved', stats.approved, '/admin/attendances?status=approved'],
    ['Rejected', stats.rejected, '/admin/attendances?status=rejected'],
    ['Late', stats.late, '/admin/attendances?is_late=true'],
  ]

  return (
    <>
      <h2>Dashboard</h2>
      <div className="tiles">
        {tiles.map(([label, value, to]) => (
          <Link key={label} to={to ?? '#'} className="tile">
            <span className="tile-value">{value}</span>
            <span className="tile-label">{label}</span>
          </Link>
        ))}
      </div>

      <h3>Recent events</h3>
      <div className="card table-wrap">
        <table>
          <thead>
            <tr><th>Event</th><th>Starts</th><th>Submissions</th><th>Turnout</th></tr>
          </thead>
          <tbody>
            {stats.recent_events.length === 0 && (
              <tr><td colSpan={4} className="muted">No events yet. <Link to="/admin/events">Create one</Link>.</td></tr>
            )}
            {stats.recent_events.map((e) => {
              const pct = e.expected ? Math.round((e.attendances / e.expected) * 100) : 0
              return (
                <tr key={e.id}>
                  <td>
                    <Link to={`/admin/attendances?event_id=${e.id}`}>{e.title}</Link>
                    {e.groups.length > 0 && <div className="small muted">{e.groups.join(', ')}</div>}
                  </td>
                  <td>{fmt(e.starts_at)}</td>
                  <td>{e.attendances} / {e.expected}</td>
                  <td>
                    <div className="bar"><div style={{ width: `${Math.min(pct, 100)}%` }} /></div>
                    <span className="small muted">{pct}%</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}
