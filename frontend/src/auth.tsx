import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, json, setUnauthorizedHandler, tokenStore, type User } from './api'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const clearSession = useCallback(() => {
    tokenStore.set(null)
    setUser(null)
  }, [])
  const logout = useCallback(async () => {
    try {
      if (tokenStore.get()) await api('/auth/logout', { method: 'POST', keepalive: true })
    } catch {
      // A lost connection still signs this browser out; the token will expire on the server.
    } finally {
      clearSession()
    }
  }, [clearSession])

  useEffect(() => {
    setUnauthorizedHandler(clearSession)
    if (!tokenStore.get()) {
      setLoading(false)
      return
    }
    api<User>('/auth/me')
      .then(setUser)
      .catch(clearSession)
      .finally(() => setLoading(false))
  }, [clearSession])

  const login = async (email: string, password: string) => {
    const res = await api<{ access_token: string; user: User }>('/auth/login', json('POST', { email, password }))
    tokenStore.set(res.access_token)
    setUser(res.user)
    return res.user
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
