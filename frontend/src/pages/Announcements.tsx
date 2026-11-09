import { useCallback, useEffect, useState } from 'react'
import { api, fmt, type Announcement } from '../api'
import { AttachmentLink, Markdown } from '../comms'
import { refreshInbox } from '../inbox'
import { ErrorNote } from '../components'

export default function Announcements() {
  const [items, setItems] = useState<Announcement[] | null>(null)
  const [openId, setOpenId] = useState<number | null>(null)
  const [onlyUnread, setOnlyUnread] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api<Announcement[]>('/announcements').then(setItems).catch((e) => setError(e.message))
  }, [])
  useEffect(load, [load])

  const toggle = async (a: Announcement) => {
    if (openId === a.id) { setOpenId(null); return }
    setOpenId(a.id)
    if (!a.read_at) {
      try {
        const updated = await api<Announcement>(`/announcements/${a.id}/read`, { method: 'POST' })
        setItems((list) => list?.map((x) => (x.id === a.id ? updated : x)) ?? null)
        refreshInbox()
      } catch (e) {
        setError((e as Error).message)
      }
    }
  }

  const unread = items?.filter((a) => !a.read_at).length ?? 0
  const shown = (items ?? []).filter((a) => !onlyUnread || !a.read_at || a.id === openId)

  return (
    <div className="narrow-wide">
      <div className="page-head">
        <h2>Announcements</h2>
        <label className="inline small">
          <input type="checkbox" checked={onlyUnread} onChange={(e) => setOnlyUnread(e.target.checked)} /> Unread only
        </label>
      </div>
      <ErrorNote error={error} />
      {!items && !error && <p className="muted">Loading…</p>}
      {items && items.length === 0 && (
        <div className="card empty-state">
          <strong>No announcements yet</strong>
          <span className="muted small">Messages from your professors show up here.</span>
        </div>
      )}
      {items && items.length > 0 && <p className="muted small">{unread ? `${unread} unread` : 'All caught up.'}</p>}
      <div className="list">
        {shown.map((a) => {
          const expanded = openId === a.id
          return (
            <article key={a.id} className={`card announcement ${a.read_at ? '' : 'unread'}`}>
              <button className="announcement-head" onClick={() => toggle(a)} aria-expanded={expanded}>
                <span className="announcement-title">
                  {!a.read_at && <span className="dot" aria-label="Unread" />}
                  <strong>{a.title}</strong>
                </span>
                <span className="muted small">{a.author_name} · {fmt(a.sent_at)}</span>
              </button>
              {expanded ? (
                <div className="announcement-body">
                  <Markdown text={a.body} />
                  {a.has_attachment && <AttachmentLink path={`/announcements/${a.id}/attachment`} name={a.attachment_name} />}
                </div>
              ) : (
                <p className="muted small clamp">{a.body.replace(/[*`#[\]]/g, '').slice(0, 200)}</p>
              )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
