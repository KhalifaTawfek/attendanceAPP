import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api, fmt, type Attendance } from '../api'
import { AuthImage, ErrorNote, StatusBadge } from '../components'

export default function MyHistory() {
  const location = useLocation()
  const submitted = (location.state as { submitted?: string } | null)?.submitted
  const [items, setItems] = useState<Attendance[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Attendance[]>('/attendances/me').then(setItems).catch((e) => setError(e.message))
  }, [])

  return (
    <>
      <h2>My attendance</h2>
      {submitted && <div className="success">Attendance for “{submitted}” submitted. An admin will review it.</div>}
      <ErrorNote error={error} />
      {items && items.length === 0 && <p className="muted">You have not submitted any attendance yet.</p>}
      <div className="list">
        {items?.map((a) => (
          <div key={a.id} className="card history">
            <AuthImage path={`/attendances/${a.id}/photo`} alt="Attendance" className="thumb" />
            <div>
              <div className="event-head">
                <strong>{a.event.title}</strong>
                <StatusBadge status={a.status} late={a.is_late} />
              </div>
              <div className="small muted">Submitted {fmt(a.submitted_at)}</div>
              <p className="small">{a.activity_summary}</p>
              {a.review_comment && <p className="small"><em>Reviewer: {a.review_comment}</em></p>}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
