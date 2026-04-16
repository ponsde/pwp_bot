/**
 * Session title management — reads from our SQLite-backed session store.
 * The OV Thread component calls `useSessionTitles().getTitle(sessionId)`.
 */
import { useSessions } from './use-sessions'

export function useSessionTitles() {
  const { sessions } = useSessions()

  function getTitle(sessionId: string): string {
    const match = sessions.find((s) => s.id === sessionId)
    return match?.title || ''
  }

  return { getTitle }
}

/** Also used by OV's generate-title flow — we set title via our backend. */
export function setSessionTitle(_sessionId: string, _title: string): void {
  // Title is set server-side by syncMessages auto-title logic.
  // This is a no-op stub for OV compatibility.
}
