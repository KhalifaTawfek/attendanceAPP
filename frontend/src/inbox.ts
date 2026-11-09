import { useEffect, useState } from 'react'
import { api, type InboxSummary } from './api'

// ---------- Nav badge counts for students ----------

let listeners: ((s: InboxSummary) => void)[] = []

/** Ask every mounted useInbox() to refetch, e.g. after reading or voting. */
export function refreshInbox() {
  api<InboxSummary>('/inbox').then((s) => listeners.forEach((l) => l(s))).catch(() => {})
}

export function useInbox(enabled: boolean): InboxSummary | null {
  const [summary, setSummary] = useState<InboxSummary | null>(null)
  useEffect(() => {
    if (!enabled) return
    listeners.push(setSummary)
    refreshInbox()
    const id = setInterval(refreshInbox, 60_000)
    return () => {
      clearInterval(id)
      listeners = listeners.filter((l) => l !== setSummary)
    }
  }, [enabled])
  return enabled ? summary : null
}

/** <input type="datetime-local"> helpers (local time) */
export const toLocalInput = (d: Date) => {
  const x = new Date(d)
  x.setMinutes(x.getMinutes() - x.getTimezoneOffset())
  return x.toISOString().slice(0, 16)
}
