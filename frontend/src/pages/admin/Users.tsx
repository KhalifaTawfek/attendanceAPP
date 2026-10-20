import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, fmt, json, type Role, type User } from '../../api'
import { useAuth } from '../../auth'
import { ErrorNote, Modal } from '../../components'

export default function Users() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState<User[] | null>(null)
  const [q, setQ] = useState('')
  const [enrolling, setEnrolling] = useState(false)
  const [resetFor, setResetFor] = useState<User | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api<User[]>(`/admin/users${q ? `?q=${encodeURIComponent(q)}` : ''}`).then(setUsers).catch((e) => setError(e.message))
  }, [q])
  useEffect(load, [load])

  const patch = async (u: User, body: Partial<User>) => {
    try {
      await api(`/admin/users/${u.id}`, json('PATCH', body))
      load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <>
      <div className="page-head">
        <h2>Users</h2>
        <div className="row">
          <input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="primary" onClick={() => setEnrolling(true)}>+ Enroll user</button>
        </div>
      </div>
      <ErrorNote error={error} />
      <div className="card table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Groups</th><th>Status</th><th>Enrolled</th><th></th></tr></thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id} className={u.is_active ? '' : 'inactive'}>
                <td>{u.full_name}</td>
                <td>{u.email}</td>
                <td>
                  <select value={u.role} disabled={u.id === me?.id}
                    onChange={(e) => patch(u, { role: e.target.value as Role })}>
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td className="small">{u.groups.map((g) => g.name).join(', ') || <span className="muted">—</span>}</td>
                <td><span className={`badge ${u.is_active ? 'approved' : 'rejected'}`}>{u.is_active ? 'active' : 'disabled'}</span></td>
                <td className="small">{fmt(u.created_at)}</td>
                <td className="actions">
                  <Link to={`/admin/attendances?user_id=${u.id}`}>Attendances</Link>
                  <button className="link" onClick={() => setResetFor(u)}>Reset password</button>
                  {u.id !== me?.id && (
                    <button className="link" onClick={() => patch(u, { is_active: !u.is_active })}>
                      {u.is_active ? 'Disable' : 'Enable'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {enrolling && <EnrollForm onClose={() => setEnrolling(false)} onSaved={() => { setEnrolling(false); load() }} />}
      {resetFor && <ResetPassword user={resetFor} onClose={() => setResetFor(null)} />}
    </>
  )
}

function EnrollForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ full_name: '', email: '', password: '', role: 'user' as Role })
  const [error, setError] = useState<string | null>(null)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api('/admin/users', json('POST', f))
      onSaved()
    } catch (err) {
      setError((err as Error).message)
    }
  }
  return (
    <Modal title="Enroll user" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <label>Full name *<input required value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></label>
        <label>Email *<input type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
        <label>Temporary password * <span className="muted small">(min 8; share it with the user)</span>
          <input required minLength={8} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></label>
        <label>Role
          <select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value as Role })}>
            <option value="user">user</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <ErrorNote error={error} />
        <div className="row end">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="primary">Enroll</button>
        </div>
      </form>
    </Modal>
  )
}

function ResetPassword({ user, onClose }: { user: User; onClose: () => void }) {
  const [pw, setPw] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api(`/admin/users/${user.id}`, json('PATCH', { password: pw }))
      setDone(true)
    } catch (err) {
      setError((err as Error).message)
    }
  }
  return (
    <Modal title={`Reset password — ${user.full_name}`} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <label>New temporary password<input required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} /></label>
        <ErrorNote error={error} />
        {done && <div className="success">Password reset.</div>}
        <div className="row end">
          <button type="button" onClick={onClose}>Close</button>
          <button className="primary" disabled={done}>Reset</button>
        </div>
      </form>
    </Modal>
  )
}
