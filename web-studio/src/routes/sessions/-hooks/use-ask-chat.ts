import { useCallback, useRef, useState } from 'react'

import { streamAsk } from '../-lib/api'
import type { AskResponse } from '../-lib/api'

export type ChatStatus = 'idle' | 'streaming' | 'error'

export interface UserChatMessage {
  id: string
  role: 'user'
  content: string
  createdAt: string
}

export interface AssistantChatMessage {
  id: string
  role: 'assistant'
  content: string
  sql: string | null
  chartUrl: string | null
  chartType: string | null
  needsClarification: boolean
  createdAt: string
}

export type ChatMessage = UserChatMessage | AssistantChatMessage

export interface UseAskChatReturn {
  messages: ChatMessage[]
  status: ChatStatus
  error: string | undefined
  streamingStatus: string
  streamingSql: string
  send: (message: string) => Promise<void>
  abort: () => void
}

function genId(): string {
  return `msg_${crypto.randomUUID().replace(/-/g, '')}`
}

function nowIso(): string {
  return new Date().toISOString()
}

export function useAskChat(): UseAskChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [status, setStatus] = useState<ChatStatus>('idle')
  const [error, setError] = useState<string | undefined>()
  const [streamingStatus, setStreamingStatus] = useState('')
  const [streamingSql, setStreamingSql] = useState('')

  const sessionIdRef = useRef<string | undefined>(undefined)
  const abortRef = useRef<AbortController | null>(null)

  const abort = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  const send = useCallback(async (message: string) => {
    const text = message.trim()
    if (!text) return
    if (status === 'streaming') return

    const userMsg: UserChatMessage = {
      id: genId(),
      role: 'user',
      content: text,
      createdAt: nowIso(),
    }
    setMessages((prev) => [...prev, userMsg])
    setStatus('streaming')
    setError(undefined)
    setStreamingStatus('正在理解问题…')
    setStreamingSql('')

    const controller = new AbortController()
    abortRef.current = controller

    let finalResponse: AskResponse | undefined
    let partialSql = ''

    try {
      for await (const ev of streamAsk({ question: text, session_id: sessionIdRef.current }, controller.signal)) {
        if (controller.signal.aborted) break
        if (ev.type === 'status') {
          setStreamingStatus(ev.payload.message || '')
        } else if (ev.type === 'sql') {
          partialSql = ev.payload.sql || ''
          setStreamingSql(partialSql)
        } else if (ev.type === 'done') {
          finalResponse = ev.payload
        } else if (ev.type === 'error') {
          throw new Error(ev.payload.message)
        }
      }

      if (finalResponse) {
        sessionIdRef.current = finalResponse.session_id
        const assistantMsg: AssistantChatMessage = {
          id: genId(),
          role: 'assistant',
          content: finalResponse.content ?? '',
          sql: finalResponse.sql,
          chartUrl: finalResponse.chart_url,
          chartType: finalResponse.chart_type,
          needsClarification: finalResponse.needs_clarification,
          createdAt: nowIso(),
        }
        setMessages((prev) => [...prev, assistantMsg])
      }
      setStatus('idle')
    } catch (err) {
      if (controller.signal.aborted) {
        setStatus('idle')
      } else {
        const msg = err instanceof Error ? err.message : String(err)
        setError(msg)
        setStatus('error')
        const assistantMsg: AssistantChatMessage = {
          id: genId(),
          role: 'assistant',
          content: `⚠️ ${msg}`,
          sql: partialSql || null,
          chartUrl: null,
          chartType: null,
          needsClarification: false,
          createdAt: nowIso(),
        }
        setMessages((prev) => [...prev, assistantMsg])
      }
    } finally {
      setStreamingStatus('')
      setStreamingSql('')
      abortRef.current = null
    }
  }, [status])

  return { messages, status, error, streamingStatus, streamingSql, send, abort }
}
