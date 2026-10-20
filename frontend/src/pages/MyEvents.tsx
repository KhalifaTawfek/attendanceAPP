import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, describeSeries, fmt, type EventItem } from '../api'
import { ErrorNote, StatusBadge } from '../components'

export default function MyEvents() {
  const [events, setEvents] = useState<EventItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<EventItem[]>('/events').then(setEvents).catch((e) => setError(e.message))
  }, [])

  const open = events?.filter((e) => e.check_in_open) ?? []
  const other = events?.filter((e) => !e.check_in_open) ?? []

  return (
    <>
      <h2>Events</h2>
      <ErrorNote error={error} />
      {!events && !error && <p className="muted">Loading…</p>}

      <h3>Check-in open now</h3>
      {events && open.length === 0 && <p className="muted">No events are open for check-in right now.</p>}
      <div className="grid">
        {open.map((e) => <EventCard key={e.id} e={e} />)}
      </div>

      {other.length > 0 && <h3>Upcoming &amp; recent</h3>}
      <div className="grid">
        {other.map((e) => <EventCard key={e.id} e={e} />)}
      </div>
    </>
  )
}

function EventCard({ e }: { e: EventItem }) {
  const upcoming = new Date(e.check_in_opens_at) > new Date()
  return (
    <div className="card event">
      <div className="event-head">
        <strong>{e.title}</strong>
        {e.my_attendance_status && <StatusBadge status={e.my_attendance_status} />}
      </div>
      <div className="muted small">{fmt(e.starts_at)} – {fmt(e.ends_at)}</div>
      {e.location && <div className="small">📍 {e.location}</div>}
      {e.series && <div className="small muted">🔁 {describeSeries(e.series)}</div>}
      {e.groups.length > 0 && <div className="small muted">👥 {e.groups.map((g) => g.name).join(', ')}</div>}
      {e.description && <p className="small">{e.description}</p>}
      <div className="event-foot">
        {e.my_attendance_status ? (
          <span className="muted small">Submitted</span>
        ) : e.check_in_open ? (
          <Link className="button primary" to={`/check-in/${e.id}`}>Check in</Link>
        ) : upcoming ? (
          <span className="muted small">Check-in opens {fmt(e.check_in_opens_at)}</span>
        ) : (
          <span className="muted small">Check-in closed</span>
        )}
      </div>
    </div>
  )
}
