import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, audienceLabel, fmt, json, relative, type GroupBrief, type Poll, type PollVoter } from '../../api'
import { AudiencePicker, PollResults } from '../../comms'
import { toLocalInput } from '../../inbox'
import { ErrorNote, Modal } from '../../components'

const LIVE_MS = 4_000
const MAX_OPTIONS = 8

export default function AdminPolls() {
  const [polls, setPolls] = useState<Poll[] | null>(null)
  const [groups, setGroups] = useState<GroupBrief[]>([])
  const [creating, setCreating] = useState(false)
  const [viewing, setViewing] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api<Poll[]>('/polls').then(setPolls).catch((e) => setError(e.message))
  }, [])
  useEffect(() => {
    load()
    api<GroupBrief[]>('/admin/groups').then(setGroups).catch(() => {})
    const id = setInterval(load, 15_000)
    return () => clearInterval(id)
  }, [load])

  const open = polls?.filter((p) => p.status === 'open') ?? []
  const closed = polls?.filter((p) => p.status === 'closed') ?? []

  return (
    <>
      <div className="page-head">
        <h2>Polls</h2>
        <button className="primary" onClick={() => setCreating(true)}>+ New poll</button>
      </div>
      <p className="muted small">Ask students to vote, e.g. on an exam date. Polls are anonymous by default: you see totals and who voted, never what they chose.</p>
      <ErrorNote error={error} />
      {polls?.length === 0 && (
        <div className="card empty-state"><strong>No polls yet</strong><span className="muted small">Create one to ask your groups a question.</span></div>
      )}
      {open.length > 0 && <h3>Open</h3>}
      <div className="grid">{open.map((p) => <PollTile key={p.id} poll={p} onOpen={() => setViewing(p.id)} />)}</div>
      {closed.length > 0 && <h3>Closed</h3>}
      <div className="grid">{closed.map((p) => <PollTile key={p.id} poll={p} onOpen={() => setViewing(p.id)} />)}</div>

      {creating && <CreatePoll groups={groups} onClose={() => setCreating(false)} onCreated={(p) => { setCreating(false); load(); setViewing(p.id) }} />}
      {viewing !== null && <PollDetails id={viewing} onClose={() => { setViewing(null); load() }} />}
    </>
  )
}

function PollTile({ poll, onOpen }: { poll: Poll; onOpen: () => void }) {
  const turnout = poll.eligible_count ? Math.round((100 * (poll.total_votes ?? 0)) / poll.eligible_count) : 0
  const leader = [...poll.options].sort((a, b) => (b.votes ?? 0) - (a.votes ?? 0))[0]
  return (
    <button className="card poll-tile" onClick={onOpen}>
      <div className="event-head">
        <strong>{poll.title}</strong>
        <span className={`badge ${poll.status}`}>{poll.status}</span>
      </div>
      <div className="muted small">{audienceLabel(poll)} · {poll.status === 'open' ? `closes ${relative(poll.closes_at)}` : `closed ${fmt(poll.closed_at ?? poll.closes_at)}`}</div>
      <div className="small"><span className="bar"><div style={{ width: `${turnout}%` }} /></span>{poll.total_votes} of {poll.eligible_count} voted</div>
      {leader && (leader.votes ?? 0) > 0 && <div className="small">Leading: <strong>{leader.label}</strong> ({Math.round(leader.percentage ?? 0)}%)</div>}
    </button>
  )
}

function CreatePoll({ groups, onClose, onCreated }: { groups: GroupBrief[]; onClose: () => void; onCreated: (p: Poll) => void }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [options, setOptions] = useState(['', ''])
  const [closesAt, setClosesAt] = useState(() => toLocalInput(new Date(Date.now() + 3 * 86_400_000)))
  const [anonymous, setAnonymous] = useState(true)
  const [all, setAll] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const setOption = (i: number, v: string) => setOptions(options.map((o, j) => (j === i ? v : o)))
  const letter = (i: number) => String.fromCharCode(65 + i)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!all && selected.size === 0) { setError('Choose at least one group, or ask everyone.'); return }
    const deadline = new Date(closesAt)
    if (Number.isNaN(deadline.getTime()) || deadline <= new Date()) { setError('The deadline must be in the future.'); return }
    setBusy(true)
    setError(null)
    try {
      const p = await api<Poll>('/polls', json('POST', {
        title, description, options: options.map((o) => o.trim()), closes_at: deadline.toISOString(),
        is_anonymous: anonymous, audience_all: all, group_ids: [...selected],
      }))
      onCreated(p)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="New poll" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <label>Question *<input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="When do you want the exam?" /></label>
        <label>Description<textarea rows={2} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <fieldset className="scope">
          <legend>Options (2–{MAX_OPTIONS})</legend>
          {options.map((o, i) => (
            <div key={i} className="row option-row">
              <span className="option-letter">{letter(i)}</span>
              <input required maxLength={200} value={o} onChange={(e) => setOption(i, e.target.value)} placeholder={`Option ${letter(i)}`} aria-label={`Option ${letter(i)}`} />
              {options.length > 2 && (
                <button type="button" className="link danger" onClick={() => setOptions(options.filter((_, j) => j !== i))} aria-label={`Remove option ${letter(i)}`}>✕</button>
              )}
            </div>
          ))}
          {options.length < MAX_OPTIONS && (
            <button type="button" className="link" onClick={() => setOptions([...options, ''])}>+ Add option</button>
          )}
        </fieldset>
        <label>Closes at *<input type="datetime-local" required value={closesAt} onChange={(e) => setClosesAt(e.target.value)} /></label>
        <AudiencePicker groups={groups} all={all} setAll={setAll} selected={selected} setSelected={setSelected} />
        <label className="check">
          <input type="checkbox" checked={anonymous} onChange={(e) => setAnonymous(e.target.checked)} />
          <span>Anonymous <span className="muted small">— you'll see totals and who voted, but not what anyone chose. Can't be changed later.</span></span>
        </label>
        <ErrorNote error={error} />
        <div className="row end">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy}>{busy ? 'Creating…' : 'Create poll'}</button>
        </div>
      </form>
    </Modal>
  )
}

function PollDetails({ id, onClose }: { id: number; onClose: () => void }) {
  const [poll, setPoll] = useState<Poll | null>(null)
  const [voters, setVoters] = useState<PollVoter[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api<Poll>(`/polls/${id}`).then(setPoll).catch((e) => setError(e.message))
    api<PollVoter[]>(`/polls/${id}/voters`).then(setVoters).catch(() => {})
  }, [id])
  useEffect(() => {
    load()
    const t = setInterval(load, LIVE_MS) // near-real-time results
    return () => clearInterval(t)
  }, [load])

  const act = async (path: string, method: string, ask: string) => {
    if (!confirm(ask)) return
    try {
      const res = await api<Poll | undefined>(path, { method })
      if (method === 'DELETE') onClose()
      else if (res) setPoll(res)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (!poll) return <Modal title="Poll" onClose={onClose}><ErrorNote error={error} />{!error && <p className="muted">Loading…</p>}</Modal>
  const labelOf = new Map(poll.options.map((o) => [o.id, o.label]))
  const voted = voters.filter((v) => v.voted)
  const waiting = voters.filter((v) => !v.voted)

  return (
    <Modal title={poll.title} onClose={onClose}>
      <div className="row">
        <span className={`badge ${poll.status}`}>{poll.status}</span>
        <span className="muted small">
          {audienceLabel(poll)} · {poll.status === 'open' ? `closes ${fmt(poll.closes_at)} (${relative(poll.closes_at)})` : `closed ${fmt(poll.closed_at ?? poll.closes_at)}`}
          {poll.is_anonymous ? ' · 🔒 anonymous' : ' · 👁 named'}
        </span>
      </div>
      {poll.description && <p className="small">{poll.description}</p>}
      <ErrorNote error={error} />
      <div className="card">
        <PollResults options={poll.options} total={poll.total_votes} />
        <div className="muted small">{poll.total_votes} of {poll.eligible_count} eligible students voted{poll.status === 'open' && ' · updates live'}</div>
      </div>
      <div className="two">
        <div>
          <h3>Voted ({voted.length})</h3>
          <ul className="plain small">
            {voted.map((v) => (
              <li key={v.user_id}>✓ {v.full_name}{v.option_id && <span className="muted"> — {labelOf.get(v.option_id)}</span>}</li>
            ))}
            {voted.length === 0 && <li className="muted">No votes yet.</li>}
          </ul>
        </div>
        <div>
          <h3>Not yet ({waiting.length})</h3>
          <ul className="plain small">{waiting.map((v) => <li key={v.user_id} className="muted">{v.full_name}</li>)}</ul>
        </div>
      </div>
      {poll.can_manage && (
        <div className="row end">
          {poll.status === 'open' && (
            <button onClick={() => act(`/polls/${id}/close`, 'POST', 'Close this poll now? Nobody else will be able to vote.')}>Close poll now</button>
          )}
          <button className="danger" onClick={() => act(`/polls/${id}`, 'DELETE', 'Delete this poll and all its votes?')}>Delete</button>
        </div>
      )}
    </Modal>
  )
}
