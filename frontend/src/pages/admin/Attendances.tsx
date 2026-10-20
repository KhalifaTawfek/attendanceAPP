import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  api, download, fmt, json, qs,
  type Attendance, type AttendancePage, type AttendanceStatus, type EventItem, type Group, type User,
} from '../../api'
import { AuthImage, ErrorNote, Modal, StatusBadge } from '../../components'

const FILTER_KEYS = ['event_id', 'user_id', 'group_id', 'status', 'is_late', 'q', 'date_from', 'date_to', 'sort'] as const
const PAGE_SIZE = 25

/** datetime-local value -> ISO with offset (backend needs a timezone) */
const toIso = (v: string | null) => (v ? new Date(v).toISOString() : undefined)

export default function Attendances() {
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<AttendancePage | null>(null)
  const [events, setEvents] = useState<EventItem[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [selected, setSelected] = useState<Attendance | null>(null)
  const [error, setError] = useState<string | null>(null)
  const page = Number(params.get('page') ?? 1)

  const filters = Object.fromEntries(
    FILTER_KEYS.map((k) => [k, k.startsWith('date_') ? toIso(params.get(k)) : params.get(k) ?? undefined]),
  )
  const filterQs = qs(filters)

  const load = useCallback(() => {
    api<AttendancePage>(`/admin/attendances${filterQs}${filterQs ? '&' : '?'}page=${page}&page_size=${PAGE_SIZE}`)
      .then(setData)
      .catch((e) => setError(e.message))
  }, [filterQs, page])

  useEffect(load, [load])
  useEffect(() => {
    api<EventItem[]>('/events?scope=all').then(setEvents).catch(() => {})
    api<User[]>('/admin/users').then(setUsers).catch(() => {})
    api<Group[]>('/admin/groups').then(setGroups).catch(() => {})
  }, [])

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value); else next.delete(key)
    next.delete('page')
    setParams(next)
  }

  const exportAs = (format: 'csv' | 'xlsx') =>
    download(`/admin/attendances/export${qs({ ...filters, format })}`, `attendances.${format}`).catch((e) =>
      setError(e.message),
    )

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <>
      <div className="page-head">
        <h2>Attendances</h2>
        <div className="row">
          <button onClick={() => exportAs('csv')}>⬇ Export CSV</button>
          <button onClick={() => exportAs('xlsx')}>⬇ Export Excel</button>
        </div>
      </div>

      <div className="card filters">
        <input placeholder="Search name, email, event…" defaultValue={params.get('q') ?? ''}
          onKeyDown={(e) => e.key === 'Enter' && setFilter('q', e.currentTarget.value)}
          onBlur={(e) => setFilter('q', e.target.value)} />
        <select value={params.get('event_id') ?? ''} onChange={(e) => setFilter('event_id', e.target.value)}>
          <option value="">All events</option>
          {events.map((e) => <option key={e.id} value={e.id}>{e.title} ({fmt(e.starts_at)})</option>)}
        </select>
        <select value={params.get('user_id') ?? ''} onChange={(e) => setFilter('user_id', e.target.value)}>
          <option value="">All users</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
        </select>
        <select value={params.get('group_id') ?? ''} onChange={(e) => setFilter('group_id', e.target.value)}>
          <option value="">All groups</option>
          {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select>
        <select value={params.get('status') ?? ''} onChange={(e) => setFilter('status', e.target.value)}>
          <option value="">Any status</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <select value={params.get('is_late') ?? ''} onChange={(e) => setFilter('is_late', e.target.value)}>
          <option value="">On time &amp; late</option>
          <option value="false">On time</option>
          <option value="true">Late</option>
        </select>
        <label className="inline">From
          <input type="datetime-local" value={params.get('date_from') ?? ''} onChange={(e) => setFilter('date_from', e.target.value)} />
        </label>
        <label className="inline">To
          <input type="datetime-local" value={params.get('date_to') ?? ''} onChange={(e) => setFilter('date_to', e.target.value)} />
        </label>
        <select value={params.get('sort') ?? '-submitted_at'} onChange={(e) => setFilter('sort', e.target.value)}>
          <option value="-submitted_at">Newest first</option>
          <option value="submitted_at">Oldest first</option>
          <option value="user">User A–Z</option>
          <option value="event">Event A–Z</option>
          <option value="status">Status</option>
        </select>
        <button className="link" onClick={() => setParams(new URLSearchParams())}>Clear</button>
      </div>

      <ErrorNote error={error} />

      <div className="card table-wrap">
        <table>
          <thead>
            <tr><th></th><th>User</th><th>Event</th><th>Submitted</th><th>Status</th><th>Summary</th></tr>
          </thead>
          <tbody>
            {data?.items.length === 0 && <tr><td colSpan={6} className="muted">No attendances match these filters.</td></tr>}
            {data?.items.map((a) => (
              <tr key={a.id} className="clickable" onClick={() => setSelected(a)}>
                <td><AuthImage path={`/attendances/${a.id}/photo`} alt="" className="mini" /></td>
                <td>{a.user.full_name}<div className="small muted">{a.user.email}</div></td>
                <td>{a.event.title}</td>
                <td>{fmt(a.submitted_at)}</td>
                <td><StatusBadge status={a.status} late={a.is_late} /></td>
                <td className="truncate">{a.activity_summary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data && (
        <div className="pager">
          <span className="muted small">{data.total} result{data.total === 1 ? '' : 's'}</span>
          <button disabled={page <= 1} onClick={() => setFilter('page', String(page - 1))}>‹ Prev</button>
          <span className="small">Page {page} / {pages}</span>
          <button disabled={page >= pages} onClick={() => setFilter('page', String(page + 1))}>Next ›</button>
        </div>
      )}

      {selected && (
        <ReviewModal
          a={selected}
          onClose={() => setSelected(null)}
          onSaved={() => { setSelected(null); load() }}
        />
      )}
    </>
  )
}

function ReviewModal({ a, onClose, onSaved }: { a: Attendance; onClose: () => void; onSaved: () => void }) {
  const [comment, setComment] = useState(a.review_comment)
  const [error, setError] = useState<string | null>(null)

  const review = async (status: AttendanceStatus) => {
    try {
      await api(`/admin/attendances/${a.id}`, json('PATCH', { status, review_comment: comment }))
      onSaved()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <Modal title={`${a.user.full_name} — ${a.event.title}`} onClose={onClose}>
      <div className="review">
        <AuthImage path={`/attendances/${a.id}/photo`} alt="Attendance photo" className="full" />
        <dl>
          <dt>Status</dt><dd><StatusBadge status={a.status} late={a.is_late} /></dd>
          <dt>Submitted</dt><dd>{fmt(a.submitted_at)}</dd>
          <dt>Event start</dt><dd>{fmt(a.event.starts_at)}</dd>
          <dt>Activity</dt><dd>{a.activity_summary}</dd>
          <dt>Location</dt><dd>{a.location_note || '—'}</dd>
          <dt>Declaration</dt><dd>{a.declaration ? 'Confirmed' : 'No'}</dd>
          {a.reviewed_at && (<><dt>Reviewed</dt><dd>{fmt(a.reviewed_at)}</dd></>)}
        </dl>
      </div>
      <label>Review comment
        <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
      </label>
      <ErrorNote error={error} />
      <div className="row end">
        <button onClick={() => review('pending')}>Mark pending</button>
        <button className="danger" onClick={() => review('rejected')}>Reject</button>
        <button className="primary" onClick={() => review('approved')}>Approve</button>
      </div>
    </Modal>
  )
}
