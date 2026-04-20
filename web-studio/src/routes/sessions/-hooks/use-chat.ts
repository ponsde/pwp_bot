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

/**
 * Stream segment: a single text run or a tool call in the order it
 * happened, so the UI can preserve the chronological interleave of
 * "text → tool → more text → another tool → …" rather than dumping all
 * tool calls above all text.
 */
export type StreamSegment =
  | { kind: 'text'; text: string }
  | { kind: 'tool'; tc: StreamToolCall }


function segmentsToParts(segments: StreamSegment[]): MessagePart[] {
  const parts: MessagePart[] = []
  for (const seg of segments) {
    if (seg.kind === 'text') {
      if (seg.text) parts.push({ type: 'text', text: seg.text } satisfies TextPart)
    } else {
      const toolPart: ToolPart = {
        type: 'tool',
        tool_id: '',
        tool_name: seg.tc.name,
        tool_uri: '',
        skill_uri: '',
        tool_status: 'completed',
        tool_output: seg.tc.result,
      }
      try {
        toolPart.tool_input = JSON.parse(seg.tc.arguments)
      } catch {
        toolPart.tool_input = { raw: seg.tc.arguments }
      }
      parts.push(toolPart)
    }
  }
  return parts
}


function buildAssistantMessage(segments: StreamSegment[]): Message {
  return {
    id: generateId(),
    role: 'assistant',
    parts: segmentsToParts(segments),
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
  streamingSegments: StreamSegment[]
  retryingId: string | null
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
  const [streamingSegments, setStreamingSegments] = useState<StreamSegment[]>([])
  const [iteration, setIteration] = useState(0)
  // When a retry is in flight, we hide the target assistant from the list
  // so the streaming bubble appears in its place rather than beneath it.
  const [retryingId, setRetryingId] = useState<string | null>(null)

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
    setStreamingSegments([])
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
    setStreamingSegments([])
    setIteration(0)
  }, [abort, initialMessages])

  /**
   * Internal send. If ``retryTargetId`` is given, we do NOT push a fresh user
   * message (the original is preserved) and on completion we append the new
   * reply as an additional version of the existing assistant message at that
   * id. Otherwise the normal flow: add user message, stream, append assistant.
   */
  const sendInternal = useCallback(async (
    message: string,
    opts: { retryTargetId?: string } = {},
  ) => {
    if (status === 'streaming') return

    const isRetry = Boolean(opts.retryTargetId)
    const isFirstExchange = !isRetry && messagesRef.current.length === 0

    if (!isRetry) {
      const userMsg = createUserMessage(message)
      setMessages((prev) => [...prev, userMsg])
    } else if (opts.retryTargetId) {
      setRetryingId(opts.retryTargetId)
    }
    setStatus('streaming')
    setError(undefined)
    setStreamingContent('')
    setStreamingToolCalls([])
    setStreamingReasoning('')
    setStreamingSegments([])
    setIteration(0)

    const controller = new AbortController()
    abortRef.current = controller

    let accContent = ''
    let accReasoning = ''
    const accToolCalls: StreamToolCall[] = []
    let lastToolCall: StreamToolCall | null = null

    // Chronological segments for interleaved text / tool rendering. Starts
    // with a single empty text bucket; content_delta appends to the last
    // text bucket; tool_call pushes a tool segment then a new text bucket
    // for any subsequent content.
    const segments: StreamSegment[] = [{ kind: 'text', text: '' }]
    const getCurrentTextSeg = (): { kind: 'text'; text: string } => {
      const last = segments[segments.length - 1]
      if (last?.kind === 'text') return last
      const fresh: { kind: 'text'; text: string } = { kind: 'text', text: '' }
      segments.push(fresh)
      return fresh
    }
    const flushSegments = () => setStreamingSegments([...segments])

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
      // Content drains into the current text segment — NOT a separate
      // displayContent string — so the rendered order reflects what
      // actually happened.
      if (contentBuffer) {
        let take = 1
        if (streamEnded) take = contentBuffer.length
        else if (contentBuffer.length > CATCH_UP_THRESHOLD) take = 8
        else if (contentBuffer.length > 30) take = 3
        const slice = contentBuffer.slice(0, take)
        contentBuffer = contentBuffer.slice(take)
        displayContent += slice
        const seg = getCurrentTextSeg()
        seg.text += slice
        flushSegments()
        setStreamingContent(displayContent)
        changed = true
      }
      if (reasoningBuffer) {
        let take = 1
        if (streamEnded) take = reasoningBuffer.length
        else if (reasoningBuffer.length > CATCH_UP_THRESHOLD) take = 8
        else if (reasoningBuffer.length > 30) take = 3
        const slice = reasoningBuffer.slice(0, take)
        reasoningBuffer = reasoningBuffer.slice(take)
        displayReasoning += slice
        setStreamingReasoning(displayReasoning)
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
            // Record a tool segment in the chronological timeline. The
            // next content_delta will open a fresh text segment after it.
            segments.push({ kind: 'tool', tc: lastToolCall })
            segments.push({ kind: 'text', text: '' })
            flushSegments()
            break
          }
          case 'tool_result': {
            if (lastToolCall) {
              lastToolCall.result = String(event.data)
              setStreamingToolCalls([...accToolCalls])
              // Tool segment holds a reference to the same StreamToolCall
              // object, so we only need to poke re-render.
              flushSegments()
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

      // Flush any undrained content into the active text segment before
      // snapshotting — otherwise the saved message is truncated at whatever
      // the typewriter had written so far.
      if (contentBuffer) {
        const seg = getCurrentTextSeg()
        seg.text += contentBuffer
        displayContent += contentBuffer
        contentBuffer = ''
      }
      if (reasoningBuffer) {
        displayReasoning += reasoningBuffer
        reasoningBuffer = ''
      }

      const assistantMsg = buildAssistantMessage(segments)
      // Build the NEXT messages list synchronously so the subsequent
      // persist call writes the same thing the UI will render — otherwise
      // retry's in-place replace and the persist-append can disagree and
      // corrupt what loads on next session open.
      let nextMessages: Message[] = messagesRef.current
      if (isRetry && opts.retryTargetId) {
        const targetId = opts.retryTargetId
        let found = false
        nextMessages = messagesRef.current.map((m) => {
          if (m.id !== targetId) return m
          found = true
          const prevVersions = m.versions ?? [m.parts]
          const versions = [...prevVersions, assistantMsg.parts]
          return {
            ...m,
            parts: assistantMsg.parts,
            versions,
            version_index: versions.length - 1,
          }
        })
        // Fallback: if the target is somehow gone from the list, append
        // so we don't lose the reply entirely.
        if (!found) nextMessages = [...messagesRef.current, assistantMsg]
      } else {
        nextMessages = [...messagesRef.current, assistantMsg]
      }
      setMessages(nextMessages)
      setRetryingId(null)
      setStatus('idle')
      setStreamingContent('')
      setStreamingToolCalls([])
      setStreamingReasoning('')
      setStreamingSegments([])

      // Persist to our SQLite store + refresh sidebar
      if (persistMessages) {
        syncMessagesToStore(sessionId, nextMessages).then(() => {
          // Refresh the session list so the new session + title appear immediately
          qc.invalidateQueries({ queryKey: ['our', 'chat', 'sessions'] })
        }).catch(() => {})
      }
    } catch (err) {
      streamEnded = true
      window.clearInterval(typerId)
      setRetryingId(null)
      if (controller.signal.aborted) {
        if (accContent || segments.some((s) => s.kind === 'tool')) {
          const partialMsg = buildAssistantMessage(segments)
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
  }, [status, sessionId, persistMessages, qc])

  /** Public send — always starts a fresh exchange. */
  const send = useCallback((message: string) => sendInternal(message), [sendInternal])

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
      const next = prev.map((m, i) => {
        if (i !== idx) return m
        const newParts = m.parts.map((p) =>
          p.type === 'text' ? { ...p, text: newContent } : p,
        )
        return { ...m, parts: newParts }
      })
      if (persistMessages) syncMessagesToStore(sessionId, next).catch(() => {})
      return next
    })
  }, [status, sessionId, persistMessages])

  const editAssistantMessage = useCallback((id: string, newContent: string) => {
    setMessages((prev) => {
      const next = prev.map((m) => {
        if (m.id !== id || m.role !== 'assistant') return m
        // The edit textarea shows all text segments joined; saving used to
        // write newContent into every text part (duplicating it and
        // scrambling segment/tool order). Now: keep tool parts in their
        // original positions, collapse all text into a single part at the
        // LAST text position so subsequent tool blocks don't appear to
        // "move below" the text. Pure-tool messages get the text appended.
        const lastTextIdx = (() => {
          for (let i = m.parts.length - 1; i >= 0; i--) {
            if (m.parts[i].type === 'text') return i
          }
          return -1
        })()
        const newParts: MessagePart[] = []
        m.parts.forEach((p, i) => {
          if (p.type === 'text') {
            if (i === lastTextIdx) newParts.push({ type: 'text', text: newContent })
            // earlier text parts are dropped; their content was already
            // merged into newContent via getTextFromParts('\n')
          } else {
            newParts.push(p)
          }
        })
        if (lastTextIdx === -1) newParts.push({ type: 'text', text: newContent })
        return { ...m, parts: newParts }
      })
      if (persistMessages) syncMessagesToStore(sessionId, next).catch(() => {})
      return next
    })
  }, [sessionId, persistMessages])

  /**
   * Retry a specific assistant message by generating an alternative reply
   * and appending it as a new version slot. The previous reply is preserved
   * under versions[] so the user can switch back via the ⟨ n/m ⟩ pager.
   */
  const retryAssistant = useCallback((assistantId: string) => {
    if (status === 'streaming') return
    const msgs = messagesRef.current
    const idx = msgs.findIndex((m) => m.id === assistantId)
    if (idx <= 0) return
    const user = msgs[idx - 1]
    if (user.role !== 'user') return
    const userText = user.parts
      .filter((p) => p.type === 'text')
      .map((p) => (p as { text: string }).text)
      .join('\n')
    void sendInternal(userText, { retryTargetId: assistantId })
  }, [status, sendInternal])

  /** Retry the last assistant reply. */
  const retry = useCallback(() => {
    const msgs = messagesRef.current
    const last = msgs[msgs.length - 1]
    if (!last || last.role !== 'assistant') return
    retryAssistant(last.id)
  }, [retryAssistant])

  /** Switch which version of an assistant message is active. */
  const switchVersion = useCallback((assistantId: string, nextIndex: number) => {
    setMessages((prev) => {
      const next = prev.map((m) => {
        if (m.id !== assistantId || !m.versions || m.versions.length <= 1) return m
        const clamped = Math.max(0, Math.min(m.versions.length - 1, nextIndex))
        return { ...m, version_index: clamped, parts: m.versions[clamped] }
      })
      if (persistMessages) syncMessagesToStore(sessionId, next).catch(() => {})
      return next
    })
  }, [sessionId, persistMessages])

  return {
    messages,
    status,
    error,
    streamingContent,
    streamingToolCalls,
    streamingReasoning,
    streamingSegments,
    retryingId,
    iteration,
    send,
    abort,
    reset,
    setMessages,
    deleteMessage,
    editUserMessage,
    editAssistantMessage,
    retry,
    retryAssistant,
    switchVersion,
  }
}
