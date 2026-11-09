/** Shared pieces for announcements and polls. */
import { Fragment, useState, type ReactNode } from 'react'
import { fetchBlob, type GroupBrief, type PollOption } from './api'

// ---------- Markdown (safe subset, rendered as React elements: no HTML is ever injected) ----------

function inline(text: string, key = 0): ReactNode[] {
  const out: ReactNode[] = []
  const re = /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\))/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const k = `${key}-${m.index}`
    if (m[2]) out.push(<strong key={k}>{m[2]}</strong>)
    else if (m[3]) out.push(<em key={k}>{m[3]}</em>)
    else if (m[4]) out.push(<code key={k}>{m[4]}</code>)
    else out.push(<a key={k} href={m[6]} target="_blank" rel="noopener noreferrer">{m[5]}</a>)
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) { i++; continue }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line)
    if (heading) {
      const Tag = (['h3', 'h4', 'h5'] as const)[heading[1].length - 1]
      blocks.push(<Tag key={i}>{inline(heading[2], i)}</Tag>)
      i++
      continue
    }
    const listRe = /^\s*([-*]|\d+\.)\s+(.*)$/
    if (listRe.test(line)) {
      const ordered = /^\s*\d+\./.test(line)
      const items: ReactNode[] = []
      while (i < lines.length && listRe.test(lines[i])) {
        items.push(<li key={i}>{inline(listRe.exec(lines[i])![2], i)}</li>)
        i++
      }
      blocks.push(ordered ? <ol key={`l${i}`}>{items}</ol> : <ul key={`l${i}`}>{items}</ul>)
      continue
    }
    const para: string[] = []
    while (i < lines.length && lines[i].trim() && !listRe.test(lines[i]) && !/^#{1,3}\s/.test(lines[i])) para.push(lines[i++])
    blocks.push(
      <p key={`p${i}`}>
        {para.map((l, j) => <Fragment key={j}>{j > 0 && <br />}{inline(l, i * 1000 + j)}</Fragment>)}
      </p>,
    )
  }
  return <div className="md">{blocks}</div>
}

// ---------- Audience picker ----------

export function AudiencePicker({ groups, all, setAll, selected, setSelected }: {
  groups: GroupBrief[]
  all: boolean
  setAll: (v: boolean) => void
  selected: Set<number>
  setSelected: (v: Set<number>) => void
}) {
  const toggle = (id: number) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id); else next.add(id)
    setSelected(next)
  }
  return (
    <fieldset className="scope">
      <legend>Send to</legend>
      <label className="inline">
        <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> Everyone (all active students)
      </label>
      {!all && (
        groups.length === 0
          ? <span className="muted small">No groups yet. Create groups under Groups, or send to everyone.</span>
          : (
            <div className="chips">
              {groups.map((g) => (
                <label key={g.id} className={`chip ${selected.has(g.id) ? 'on' : ''}`}>
                  <input type="checkbox" checked={selected.has(g.id)} onChange={() => toggle(g.id)} />
                  {g.name}
                </label>
              ))}
            </div>
          )
      )}
    </fieldset>
  )
}

// ---------- Poll results ----------

export function PollResults({ options, myOptionId, total }: { options: PollOption[]; myOptionId?: number | null; total: number | null }) {
  const max = Math.max(1, ...options.map((o) => o.votes ?? 0))
  return (
    <div className="poll-results" role="list">
      {options.map((o) => {
        const leader = (o.votes ?? 0) === max && (o.votes ?? 0) > 0
        return (
          <div key={o.id} className={`poll-result ${leader ? 'leader' : ''}`} role="listitem">
            <div className="poll-result-head">
              <span>{o.label}{o.id === myOptionId && <span className="badge approved">your vote</span>}</span>
              <span className="muted small">{o.votes} · {Math.round(o.percentage ?? 0)}%</span>
            </div>
            <div className="poll-track"><span style={{ width: `${o.percentage ?? 0}%` }} /></div>
          </div>
        )
      })}
      <div className="muted small">{total ?? 0} vote{total === 1 ? '' : 's'}</div>
    </div>
  )
}

// ---------- Attachments ----------

export function AttachmentLink({ path, name }: { path: string; name: string | null }) {
  const [busy, setBusy] = useState(false)
  const open = async () => {
    setBusy(true)
    try {
      const { blob } = await fetchBlob(path)
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } finally {
      setBusy(false)
    }
  }
  return <button type="button" className="link" onClick={open} disabled={busy}>📎 {name ?? 'Attachment'}</button>
}
