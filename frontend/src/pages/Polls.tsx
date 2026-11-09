import { useCallback, useEffect, useState } from 'react'
import { api, fmt, json, relative, type Poll } from '../api'
import { PollResults } from '../comms'
import { refreshInbox } from '../inbox'
import { ErrorNote } from '../components'

const POLL_MS = 15_000

export default function Polls() {
  const [polls, setPolls] = useState<Poll[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api<Poll[]>('/polls').then(setPolls).catch((e) => setError(e.message))
  }, [])
  useEffect(() => {
    load()
    const id = setInterval(load, POLL_MS)
    return () => clearInterval(id)
  }, [load])

  const replace = (p: Poll) => setPolls((list) => list?.map((x) => (x.id === p.id ? p : x)) ?? null)
  const open = polls?.filter((p) => p.status === 'open') ?? []
  const closed = polls?.filter((p) => p.status === 'closed') ?? []

  return (
    <div className="narrow-wide">
      <h2>Polls</h2>
      <ErrorNote error={error} />
      {!polls && !error && <p className="muted">Loading…</p>}

      <h3>Open</h3>
      {polls && open.length === 0 && <p className="muted">No open polls right now.</p>}
      <div className="list">{open.map((p) => <PollCard key={p.id} poll={p} onChange={replace} />)}</div>

      {closed.length > 0 && <h3>Closed</h3>}
      <div className="list">{closed.map((p) => <PollCard key={p.id} poll={p} onChange={replace} />)}</div>
    </div>
  )
}

function PollCard({ poll, onChange }: { poll: Poll; onChange: (p: Poll) => void }) {
  const [choice, setChoice] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const canVote = poll.status === 'open' && !poll.has_voted

  const submit = async () => {
    if (choice === null) return
    const label = poll.options.find((o) => o.id === choice)?.label
    if (!confirm(`Vote for "${label}"? Votes are final and can't be changed.`)) return
    setBusy(true)
    setError(null)
    try {
      onChange(await api<Poll>(`/polls/${poll.id}/votes`, json('POST', { option_id: choice })))
      refreshInbox()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="card poll">
      <div className="event-head">
        <strong>{poll.title}</strong>
        <span className={`badge ${poll.status === 'open' ? (poll.has_voted ? 'approved' : 'pending') : ''}`}>
          {poll.status === 'open' ? (poll.has_voted ? 'voted' : 'open') : 'closed'}
        </span>
      </div>
      {poll.description && <p className="small">{poll.description}</p>}
      <div className="muted small">
        {poll.author_name} · {poll.status === 'open' ? `closes ${relative(poll.closes_at)} (${fmt(poll.closes_at)})` : `closed ${fmt(poll.closed_at ?? poll.closes_at)}`}
        {poll.is_anonymous ? ' · 🔒 anonymous' : ' · 👁 your name is visible to the professor'}
      </div>

      {canVote ? (
        <form className="poll-options" onSubmit={(e) => { e.preventDefault(); submit() }}>
          {poll.options.map((o) => (
            <label key={o.id} className={`poll-option ${choice === o.id ? 'on' : ''}`}>
              <input type="radio" name={`poll-${poll.id}`} checked={choice === o.id} onChange={() => setChoice(o.id)} />
              <span>{o.label}</span>
            </label>
          ))}
          <ErrorNote error={error} />
          <div className="row">
            <button className="primary" disabled={choice === null || busy}>{busy ? 'Voting…' : 'Vote'}</button>
            <span className="muted small">One vote, final. Results show after you vote.</span>
          </div>
        </form>
      ) : poll.results_visible ? (
        <>
          {poll.has_voted && poll.status === 'open' && <div className="success">Thanks, your vote was counted.</div>}
          <PollResults options={poll.options} myOptionId={poll.my_option_id} total={poll.total_votes} />
        </>
      ) : null}
    </article>
  )
}
