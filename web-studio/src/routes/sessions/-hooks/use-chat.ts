/**
 * useChat — adapted from OV's use-chat.ts to talk to vikingbot + our SQLite.
 *
 * Interface matches what OV's Thread component expects:
 *   useChat({ sessionId, initialMessages?, persistMessages? }) → UseChatReturn
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import type { ChatStatus, StreamToolCall } from '../-types/chat'
import type { Message, MessagePart, TextPart, ToolPart } from '../-types/message'
import { sendChatStream, syncMessagesToStore } from '../-lib/api'
import { parseSseStream } from '../-lib/sse'
import { setSessionTitle } from './use-session-titles'

function generateId(): string {
  return `msg_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function createUserMessage(content: string): Message {
  return {
    id: generateId(),
    role: 'user',
    parts: [{ type: 'text', text: content }],
    created_at: new Date().toISOString(),
  }
}

function buildAssistantMessage(
  content: string,
  toolCalls: StreamToolCall[],
): Message {
  const parts: MessagePart[] = []

  for (const tc of toolCalls) {
    const toolPart: ToolPart = {
      type: 'tool',
      tool_id: '',
      tool_name: tc.name,
      tool_uri: '',
      skill_uri: '',
      tool_status: 'completed',
      tool_output: tc.result,
    }
    try {
      toolPart.tool_input = JSON.parse(tc.arguments)
    } catch {
      toolPart.tool_input = { raw: tc.arguments }
    }
    parts.push(toolPart)
  }

  if (content) {
    parts.push({ type: 'text', text: content } satisfies TextPart)
  }

  return {
    id: generateId(),
    role: 'assistant',
    parts,
    created_at: new Date().toISOString(),
  }
}

export interface UseChatOptions {
  sessionId: string
  initialMessages?: Message[]
  persistMessages?: boolean
}

export interface UseChatReturn {
  messages: Message[]
  status: ChatStatus
  error: string | undefined
  streamingContent: string
  streamingToolCalls: StreamToolCall[]
  streamingReasoning: string
  iteration: number
  send: (message: string) => Promise<void>
  abort: () => void
  reset: () => void
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const { sessionId, initialMessages, persistMessages = true } = options
  const qc = useQueryClient()

  const [messages, setMessages] = useState<Message[]>(initialMessages ?? [])
  const [status, setStatus] = useState<ChatStatus>('idle')
  const [error, setError] = useState<string>()
  const [streamingContent, setStreamingContent] = useState('')
  const [streamingToolCalls, setStreamingToolCalls] = useState<StreamToolCall[]>([])
  const [streamingReasoning, setStreamingReasoning] = useState('')
  const [iteration, setIteration] = useState(0)

  const abortRef = useRef<AbortController | null>(null)
  const messagesRef = useRef<Message[]>(messages)
  messagesRef.current = messages

  useEffect(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setMessages([])
    setStatus('idle')
    setError(undefined)
    setStreamingContent('')
    setStreamingToolCalls([])
    setStreamingReasoning('')
    setIteration(0)
  }, [sessionId])

  useEffect(() => {
    if (initialMessages && initialMessages.length > 0 && status !== 'streaming') {
      setMessages(initialMessages)
    }
  }, [initialMessages]) // eslint-disable-line react-hooks/exhaustive-deps

  const abort = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  const reset = useCallback(() => {
    abort()
    setMessages(initialMessages ?? [])
    setStatus('idle')
    setError(undefined)
    setStreamingContent('')
    setStreamingToolCalls([])
    setStreamingReasoning('')
    setIteration(0)
  }, [abort, initialMessages])

  const send = useCallback(async (message: string) => {
    if (status === 'streaming') return

    const isFirstExchange = messagesRef.current.length === 0

    const userMsg = createUserMessage(message)
    setMessages((prev) => [...prev, userMsg])
    setStatus('streaming')
    setError(undefined)
    setStreamingContent('')
    setStreamingToolCalls([])
    setStreamingReasoning('')
    setIteration(0)

    const controller = new AbortController()
    abortRef.current = controller

    let accContent = ''
    let accReasoning = ''
    const accToolCalls: StreamToolCall[] = []
    let lastToolCall: StreamToolCall | null = null

    // ── Typewriter throttle ────────────────────────────────────────────
    // The bot emits content_delta chunks in bursts (~100–200 ms apart,
    // each ~20 chars). That reads as "text appearing in clumps" even
    // though it IS streaming. Buffer all incoming chars and drain at a
    // steady ~45 chars/s (~22 ms/char) for a typewriter feel. When the
    // buffer grows past 80 chars we speed up so we never fall far behind.
    let displayContent = ''
    let contentBuffer = ''
    let displayReasoning = ''
    let reasoningBuffer = ''
    let streamEnded = false
    const TICK_MS = 22
    const CATCH_UP_THRESHOLD = 80
    const typerId = window.setInterval(() => {
      let changed = false
      for (const state of [
        { label: 'content' as const },
        { label: 'reasoning' as const },
      ]) {
        const buf = state.label === 'content' ? contentBuffer : reasoningBuffer
        if (!buf) continue
        // Take 1 char by default; up to 8 when buffer is long; flush all on end.
        let take = 1
        if (streamEnded) take = buf.length
        else if (buf.length > CATCH_UP_THRESHOLD) take = 8
        else if (buf.length > 30) take = 3
        const slice = buf.slice(0, take)
        if (state.label === 'content') {
          displayContent += slice
          contentBuffer = buf.slice(take)
          setStreamingContent(displayContent)
        } else {
          displayReasoning += slice
          reasoningBuffer = buf.slice(take)
          setStreamingReasoning(displayReasoning)
        }
        changed = true
      }
      if (streamEnded && !changed) {
        window.clearInterval(typerId)
      }
    }, TICK_MS)

    try {
      const response = await sendChatStream(
        { message, session_id: sessionId },
        controller.signal,
      )

      for await (const event of parseSseStream(response)) {
        if (controller.signal.aborted) break

        switch (event.event) {
          case 'iteration': {
            const data = String(event.data)
            const match = data.match(/(\d+)/)
            if (match) setIteration(Number(match[1]))
            break
          }
          case 'content_delta': {
            accContent += String(event.data)
            contentBuffer += String(event.data)
            break
          }
          case 'reasoning_delta': {
            accReasoning += String(event.data)
            reasoningBuffer += String(event.data)
            break
          }
          case 'reasoning': {
            if (!accReasoning) {
              accReasoning = String(event.data)
              setStreamingReasoning(accReasoning)
            }
            break
          }
          case 'tool_call': {
            const raw = String(event.data)
            const parenIdx = raw.indexOf('(')
            const name = parenIdx > 0 ? raw.slice(0, parenIdx) : raw
            const args = parenIdx > 0 ? raw.slice(parenIdx + 1, -1) : ''
            lastToolCall = { name, arguments: args }
            accToolCalls.push(lastToolCall)
            setStreamingToolCalls([...accToolCalls])
            break
          }
          case 'tool_result': {
            if (lastToolCall) {
              lastToolCall.result = String(event.data)
              setStreamingToolCalls([...accToolCalls])
            }
            break
          }
          case 'response': {
            // If no deltas streamed (old bot), push the whole response into
            // the typewriter buffer so it still plays out visibly.
            const full = String(event.data)
            if (!accContent) {
              accContent = full
              contentBuffer += full
            } else if (full.length > accContent.length) {
              // Deltas landed short of the final text — append the tail.
              contentBuffer += full.slice(accContent.length)
              accContent = full
            }
            break
          }
        }
      }

      // Stream done; let the typewriter drain any remaining buffer, then
      // commit. We do NOT clear streamingContent immediately because that
      // would un-render the typing animation mid-word.
      streamEnded = true

      const assistantMsg = buildAssistantMessage(accContent, accToolCalls)
      setMessages((prev) => [...prev, assistantMsg])
      setStatus('idle')
      setStreamingContent('')
      setStreamingToolCalls([])
      setStreamingReasoning('')

      // Persist to our SQLite store + refresh sidebar
      if (persistMessages) {
        const allMessages = [...messagesRef.current, assistantMsg]
        syncMessagesToStore(sessionId, allMessages).then(() => {
          // Refresh the session list so the new session + title appear immediately
          qc.invalidateQueries({ queryKey: ['our', 'chat', 'sessions'] })
        }).catch(() => {})
      }
    } catch (err) {
      streamEnded = true
      window.clearInterval(typerId)
      if (controller.signal.aborted) {
        if (accContent) {
          const partialMsg = buildAssistantMessage(accContent, accToolCalls)
          setMessages((prev) => [...prev, partialMsg])
        }
        setStatus('idle')
      } else {
        const msg = err instanceof Error ? err.message : String(err)
        setError(msg)
        setStatus('error')
      }
    } finally {
      abortRef.current = null
    }
  }, [status, sessionId, persistMessages])

  const deleteMessage = useCallback((id: string) => {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === id)
      if (idx === -1) return prev
      let next: Message[]
      if (prev[idx].role === 'user' && prev[idx + 1]?.role === 'assistant') {
        next = [...prev.slice(0, idx), ...prev.slice(idx + 2)]
      } else {
        next = [...prev.slice(0, idx), ...prev.slice(idx + 1)]
      }
      if (persistMessages) syncMessagesToStore(sessionId, next).then(() => {
        qc.invalidateQueries({ queryKey: ['our', 'chat', 'sessions'] })
      }).catch(() => {})
      return next
    })
  }, [sessionId, persistMessages, qc])

  const editUserMessage = useCallback((id: string, newContent: string) => {
    if (status === 'streaming') return
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === id)
      if (idx === -1 || prev[idx].role !== 'user') return prev
      return prev.slice(0, idx)
    })
    setTimeout(() => { void send(newContent) }, 0)
  }, [status, send])

  const editAssistantMessage = useCallback((id: string, newContent: string) => {
    setMessages((prev) => {
      const next = prev.map((m) => {
        if (m.id !== id || m.role !== 'assistant') return m
        const newParts = m.parts.map((p) => p.type === 'text' ? { ...p, text: newContent } : p)
        return { ...m, parts: newParts }
      })
      if (persistMessages) syncMessagesToStore(sessionId, next).catch(() => {})
      return next
    })
  }, [sessionId, persistMessages])

  const retry = useCallback(() => {
    if (status === 'streaming') return
    setMessages((prev) => {
      if (prev.length < 2) return prev
      const last = prev[prev.length - 1]
      if (last.role !== 'assistant') return prev
      const userMsg = prev[prev.length - 2]
      if (userMsg.role !== 'user') return prev
      const userText = userMsg.parts.filter((p) => p.type === 'text').map((p) => (p as { text: string }).text).join('\n')
      const trimmed = prev.slice(0, -1)
      setTimeout(() => { void send(userText) }, 0)
      return trimmed
    })
  }, [status, send])

  return {
    messages,
    status,
    error,
    streamingContent,
    streamingToolCalls,
    streamingReasoning,
    iteration,
    send,
    abort,
    reset,
    setMessages,
    deleteMessage,
    editUserMessage,
    editAssistantMessage,
    retry,
  }
}
