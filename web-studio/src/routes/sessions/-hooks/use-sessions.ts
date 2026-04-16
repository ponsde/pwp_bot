import { useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Message } from '../-types/message'
import { deleteSession, listSessions, loadSessionMessages } from '../-lib/api'

const SESSIONS_KEY = ['our', 'chat', 'sessions'] as const
const MESSAGES_KEY = (id: string) => ['our', 'chat', 'messages', id] as const

// ---------------------------------------------------------------------------
// useSessionMessages — loads history for a single session from our SQLite
// ---------------------------------------------------------------------------

export function useSessionMessages(sessionId: string) {
  return useQuery<Message[]>({
    queryKey: MESSAGES_KEY(sessionId),
    queryFn: ({ signal }) => loadSessionMessages(sessionId, signal),
    staleTime: 0,
    refetchOnWindowFocus: false,
  })
}

// ---------------------------------------------------------------------------
// useSessions — session list CRUD
// ---------------------------------------------------------------------------

export function useSessions() {
  const qc = useQueryClient()

  const query = useQuery({
    queryKey: SESSIONS_KEY,
    queryFn: ({ signal }) => listSessions(signal),
    staleTime: 5_000,
    refetchOnWindowFocus: false,
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: SESSIONS_KEY }),
  })

  const remove = useCallback(
    async (id: string): Promise<void> => { await deleteMut.mutateAsync(id) },
    [deleteMut],
  )

  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: SESSIONS_KEY })
  }, [qc])

  return {
    sessions: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
    remove,
    refresh,
  }
}
