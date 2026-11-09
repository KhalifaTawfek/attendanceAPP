import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, json } from '../api'
import { useAuth } from '../auth'
import { ErrorNote } from '../components'

export default function Account() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (next !== confirm) return setError('New passwords do not match.')
    setError(null)
    try {
      await api('/auth/change-password', json('POST', { current_password: current, new_password: next }))
      await logout()
      navigate('/login?password_changed=1', { replace: true })
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <div className="narrow">
      <h2>Account</h2>
      <div className="card">
        <div><strong>{user?.full_name}</strong></div>
        <div className="muted">{user?.email} · {user?.role}</div>
      </div>
      <h3>Change password</h3>
      <form className="card form" onSubmit={submit}>
        <label>Current password
          <input type="password" required value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
        </label>
        <label>New password (min 8 characters)
          <input type="password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />
        </label>
        <label>Confirm new password
          <input type="password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
        </label>
        <ErrorNote error={error} />
        <button className="primary">Update password</button>
      </form>
    </div>
  )
}
