import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, audienceLabel, fmt, json, type Announcement, type AnnouncementReader, type GroupBrief } from '../../api'
import { AttachmentLink, AudiencePicker, Markdown } from '../../comms'
import { ErrorNote, Modal } from '../../components'

export default function AdminAnnouncements() {
  const [items, setItems] = useState<Announcement[] | null>(null)
  const [groups, setGroups] = useState<GroupBrief[]>([])
  const [composing, setComposing] = useState(false)
  const [viewing, setViewing] = useState<Announcement | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api<Announcement[]>('/announcements').then(setItems).catch((e) => setError(e.message))
    api<GroupBrief[]>('/admin/groups').then(setGroups).catch(() => {})
  }, [])
  useEffect(load, [load])

  const remove = async (a: Announcement) => {
    if (!confirm(`Delete "${a.title}"? Students will no longer see it.`)) return
    try {
      await api(`/announcements/${a.id}`, { method: 'DELETE' })
      setViewing(null)
      load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <>
      <div className="page-head">
        <h2>Announcements</h2>
        <button className="primary" onClick={() => setComposing(true)}>+ New announcement</button>
      </div>
      <p className="muted small">Send a newsletter to everyone or to specific groups. Students see it under Announcements and can mark it read.</p>
      <ErrorNote error={error} />
      {items?.length === 0 && (
        <div className="card empty-state">
          <strong>Nothing sent yet</strong>
          <span className="muted small">Your first announcement will be listed here with how many students have read it.</span>
        </div>
      )}
      <div className="list">
        {items?.map((a) => {
          const pct = a.recipient_count ? Math.round((100 * (a.read_count ?? 0)) / a.recipient_count) : 0
          return (
            <article key={a.id} className="card announcement clickable" onClick={() => setViewing(a)}>
              <div className="event-head">
                <strong>{a.title}</strong>
                <span className="muted small">{fmt(a.sent_at)}</span>
              </div>
              <div className="muted small">To {audienceLabel(a)} · by {a.author_name}{a.has_attachment && ' · 📎'}</div>
              <div className="small">
                <span className="bar"><div style={{ width: `${pct}%` }} /></span>
                Read by {a.read_count} of {a.recipient_count}
              </div>
            </article>
          )
        })}
      </div>
      {composing && <Compose groups={groups} onClose={() => setComposing(false)} onSent={() => { setComposing(false); load() }} />}
      {viewing && <Details a={viewing} onClose={() => setViewing(null)} onDelete={() => remove(viewing)} />}
    </>
  )
}

function Compose({ groups, onClose, onSent }: { groups: GroupBrief[]; onClose: () => void; onSent: () => void }) {
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [all, setAll] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!all && selected.size === 0) { setError('Choose at least one group, or send to everyone.'); return }
    setBusy(true)
    setError(null)
    try {
      const sent = await api<Announcement>('/announcements', json('POST', { title, body, audience_all: all, group_ids: [...selected] }))
      if (file) {
        const form = new FormData()
        form.append('file', file)
        try {
          await api(`/announcements/${sent.id}/attachment`, { method: 'POST', body: form })
        } catch (err) {
          alert(`The announcement was sent, but the attachment failed: ${(err as Error).message}`)
        }
      }
      onSent()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="New announcement" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <label>Title *<input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Exam moved to Friday" /></label>
        <div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <strong className="small">Message *</strong>
            <div className="seg">
              <button type="button" className={preview ? '' : 'on'} onClick={() => setPreview(false)}>Write</button>
              <button type="button" className={preview ? 'on' : ''} onClick={() => setPreview(true)}>Preview</button>
            </div>
          </div>
          {preview
            ? <div className="card md-preview">{body.trim() ? <Markdown text={body} /> : <span className="muted small">Nothing to preview.</span>}</div>
            : <textarea required rows={9} maxLength={20000} value={body} onChange={(e) => setBody(e.target.value)}
                placeholder={'Write your message. Markdown works: **bold**, *italic*, - lists, [link](https://…)'} />}
        </div>
        <AudiencePicker groups={groups} all={all} setAll={setAll} selected={selected} setSelected={setSelected} />
        <label>Attachment (optional, PDF or image, max 5 MB)
          <input type="file" accept="application/pdf,image/jpeg,image/png,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <ErrorNote error={error} />
        <div className="row end">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy}>{busy ? 'Sending…' : 'Send'}</button>
        </div>
      </form>
    </Modal>
  )
}

function Details({ a, onClose, onDelete }: { a: Announcement; onClose: () => void; onDelete: () => void }) {
  const [readers, setReaders] = useState<AnnouncementReader[] | null>(null)
  useEffect(() => {
    api<AnnouncementReader[]>(`/announcements/${a.id}/readers`).then(setReaders).catch(() => setReaders([]))
  }, [a.id])
  const unread = readers?.filter((r) => !r.read_at) ?? []
  return (
    <Modal title={a.title} onClose={onClose}>
      <div className="muted small">To {audienceLabel(a)} · {fmt(a.sent_at)} · by {a.author_name}</div>
      <div className="card"><Markdown text={a.body} /></div>
      {a.has_attachment && <AttachmentLink path={`/announcements/${a.id}/attachment`} name={a.attachment_name} />}
      <h3>Read by {a.read_count} of {a.recipient_count}</h3>
      {readers && unread.length > 0 && (
        <details>
          <summary className="small">{unread.length} haven't opened it</summary>
          <ul className="plain small">{unread.map((r) => <li key={r.user_id}>{r.full_name} <span className="muted">{r.email}</span></li>)}</ul>
        </details>
      )}
      {a.can_manage && (
        <div className="row end"><button className="danger" onClick={onDelete}>Delete announcement</button></div>
      )}
    </Modal>
  )
}
