import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, json, type Group, type User } from '../../api'
import { ErrorNote, Modal } from '../../components'

export default function Groups() {
  const [groups, setGroups] = useState<Group[] | null>(null)
  const [users, setUsers] = useState<User[]>([])
  const [editing, setEditing] = useState<Group | 'new' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api<Group[]>('/admin/groups').then(setGroups).catch((e) => setError(e.message))
    api<User[]>('/admin/users').then(setUsers).catch(() => {})
  }, [])
  useEffect(load, [load])

  const byId = new Map(users.map((u) => [u.id, u]))

  const remove = async (g: Group) => {
    if (!confirm(`Delete group "${g.name}"? Events limited to it become open to everyone (if it was their only group).`)) return
    try {
      await api(`/admin/groups/${g.id}`, { method: 'DELETE' })
      load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <>
      <div className="page-head">
        <h2>Groups</h2>
        <button className="primary" onClick={() => setEditing('new')}>+ New group</button>
      </div>
      <p className="muted small">
        Assign groups to an event to limit who sees it and who is expected to attend. Events without groups are open to everyone.
      </p>
      <ErrorNote error={error} />
      <div className="card table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Members</th><th></th></tr></thead>
          <tbody>
            {groups?.length === 0 && <tr><td colSpan={3} className="muted">No groups yet.</td></tr>}
            {groups?.map((g) => (
              <tr key={g.id}>
                <td><strong>{g.name}</strong>{g.description && <div className="small muted">{g.description}</div>}</td>
                <td className="small">
                  {g.member_ids.length} member{g.member_ids.length === 1 ? '' : 's'}
                  <div className="muted truncate">
                    {g.member_ids.map((id) => byId.get(id)?.full_name).filter(Boolean).join(', ')}
                  </div>
                </td>
                <td className="actions">
                  <Link to={`/admin/attendances?group_id=${g.id}`}>Attendances</Link>
                  <button className="link" onClick={() => setEditing(g)}>Edit</button>
                  <button className="link danger" onClick={() => remove(g)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && (
        <GroupForm group={editing === 'new' ? null : editing} users={users}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />
      )}
    </>
  )
}

function GroupForm({ group, users, onClose, onSaved }: {
  group: Group | null; users: User[]; onClose: () => void; onSaved: () => void
}) {
  const [name, setName] = useState(group?.name ?? '')
  const [description, setDescription] = useState(group?.description ?? '')
  const [members, setMembers] = useState<Set<number>>(new Set(group?.member_ids ?? []))
  const [q, setQ] = useState('')
  const [error, setError] = useState<string | null>(null)

  const toggle = (id: number) => {
    const next = new Set(members)
    if (next.has(id)) next.delete(id); else next.add(id)
    setMembers(next)
  }
  const shown = users.filter((u) => u.is_active && `${u.full_name} ${u.email}`.toLowerCase().includes(q.toLowerCase()))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const body = { name, description, member_ids: [...members] }
    try {
      if (group) await api(`/admin/groups/${group.id}`, json('PATCH', body))
      else await api('/admin/groups', json('POST', body))
      onSaved()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <Modal title={group ? 'Edit group' : 'New group'} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <label>Name *<input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label>Description<input value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <strong className="small">Members ({members.size})</strong>
            <input placeholder="Filter users…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="checklist">
            {shown.map((u) => (
              <label key={u.id} className="check">
                <input type="checkbox" checked={members.has(u.id)} onChange={() => toggle(u.id)} />
                <span>{u.full_name} <span className="muted small">{u.email}</span></span>
              </label>
            ))}
          </div>
        </div>
        <ErrorNote error={error} />
        <div className="row end">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="primary">{group ? 'Save' : 'Create group'}</button>
        </div>
      </form>
    </Modal>
  )
}
