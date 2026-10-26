import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, fmt, type EventItem } from '../api'
import { ErrorNote } from '../components'
import { ROOM_FLOORS, ROOMS } from '../rooms'

const MAX_MB = 5

export default function CheckIn() {
  const { eventId } = useParams()
  const navigate = useNavigate()
  const [event, setEvent] = useState<EventItem | null>(null)
  const [photo, setPhoto] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [summary, setSummary] = useState('')
  const [locationNote, setLocationNote] = useState('')
  const [declaration, setDeclaration] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<EventItem>(`/events/${eventId}`)
      .then((ev) => {
        setEvent(ev)
        if (ROOMS.includes(ev.location)) setLocationNote(ev.location)   // start from the event's room
      })
      .catch((e) => setError(e.message))
  }, [eventId])

  useEffect(() => {
    if (!photo) return setPreview(null)
    const url = URL.createObjectURL(photo)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [photo])

  const pickPhoto = (f: File | undefined) => {
    setError(null)
    if (!f) return setPhoto(null)
    if (!/^image\/(jpeg|png|webp)$/.test(f.type)) return setError('Photo must be JPEG, PNG or WebP.')
    if (f.size > MAX_MB * 1024 * 1024) return setError(`Photo must be smaller than ${MAX_MB} MB.`)
    setPhoto(f)
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!photo) return setError('Please add a photo of your presence.')
    if (!declaration) return setError('Please confirm the declaration.')
    const fd = new FormData()
    fd.set('event_id', String(eventId))
    fd.set('activity_summary', summary)
    fd.set('location_note', locationNote)
    fd.set('declaration', 'true')
    fd.set('photo', photo)
    setBusy(true)
    setError(null)
    try {
      await api('/attendances', { method: 'POST', body: fd })
      navigate('/history', { replace: true, state: { submitted: event?.title } })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!event) return error ? <ErrorNote error={error} /> : <p className="muted">Loading…</p>

  const blocked = !event.check_in_open || !!event.my_attendance_status

  return (
    <div className="narrow">
      <Link to="/" className="small">← Back to events</Link>
      <h2>Check in: {event.title}</h2>
      <p className="muted">
        {fmt(event.starts_at)} – {fmt(event.ends_at)} {event.location && `· ${event.location}`}
      </p>
      {event.my_attendance_status && <div className="info">You already submitted attendance for this event.</div>}
      {!event.check_in_open && <div className="info">Check-in is not open for this event.</div>}

      <form className="card form" onSubmit={submit}>
        <label>
          Photo of your presence *
          <input type="file" accept="image/jpeg,image/png,image/webp" capture="user"
            onChange={(e) => pickPhoto(e.target.files?.[0])} disabled={blocked} />
        </label>
        {preview && <img className="preview" src={preview} alt="Selected" />}

        <label>
          What are you doing / attending? *
          <textarea required minLength={3} maxLength={2000} rows={3} value={summary}
            onChange={(e) => setSummary(e.target.value)} disabled={blocked}
            placeholder="e.g. Attending the morning workshop, table 3" />
        </label>

        <label>
          Which room are you in? <span className="muted">(optional)</span>
          <select value={locationNote} onChange={(e) => setLocationNote(e.target.value)} disabled={blocked}>
            <option value="">Not in a listed room</option>
            {ROOM_FLOORS.map((fl) => (
              <optgroup key={fl.label} label={fl.label}>
                {fl.rooms.map((r) => <option key={r}>{r}</option>)}
              </optgroup>
            ))}
          </select>
        </label>

        <label className="check">
          <input type="checkbox" checked={declaration} onChange={(e) => setDeclaration(e.target.checked)}
            disabled={blocked} />
          I confirm that I am personally present at this event and the photo was taken now.
        </label>

        <ErrorNote error={error} />
        <button className="primary" disabled={busy || blocked}>{busy ? 'Submitting…' : 'Submit attendance'}</button>
      </form>
    </div>
  )
}
