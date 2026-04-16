/**
 * API layer — vikingbot for chat, our FastAPI for persistence.
 */

// ---------------------------------------------------------------------------
// VikingBot endpoints (chat streaming)
// ---------------------------------------------------------------------------

// Bot requests go to same-origin — FastAPI reverse-proxies /bot/v1/* to vikingbot.
const BOT_BASE =
  typeof import.meta.env.VITE_API_BASE_URL === 'string'
    ? import.meta.env.VITE_API_BASE_URL.trim().replace(/\/+$/, '')
    : ''

const API_KEY =
  typeof import.meta.env.VITE_VIKINGBOT_API_KEY === 'string'
    ? import.meta.env.VITE_VIKINGBOT_API_KEY.trim()
    : 'taidi-bot-key-2026'

function botUrl(path: string): string {
  return `${BOT_BASE}${path}`
}

function botHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
  }
}

export interface ChatRequest {
  message: string
  session_id?: string
}

export async function sendChatStream(
  req: ChatRequest,
  signal?: AbortSignal,
): Promise<Response> {
  const res = await fetch(botUrl('/bot/v1/chat/stream'), {
    method: 'POST',
    headers: botHeaders(),
    body: JSON.stringify({ ...req, stream: true }),
    signal,
  })
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '')
    throw new Error(`chat/stream failed (${res.status}): ${text || res.statusText}`)
  }
  return res
}

// ---------------------------------------------------------------------------
// Our FastAPI backend (SQLite persistence)
// ---------------------------------------------------------------------------

const OUR_BASE =
  typeof import.meta.env.VITE_API_BASE_URL === 'string'
    ? import.meta.env.VITE_API_BASE_URL.trim().replace(/\/+$/, '')
    : ''

function ourUrl(path: string): string {
  return `${OUR_BASE}${path}`
}

export interface SessionMeta {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export async function listSessions(signal?: AbortSignal): Promise<SessionMeta[]> {
  const res = await fetch(ourUrl('/api/chat/sessions'), { signal })
  if (!res.ok) return []
  const data = (await res.json()) as { sessions?: SessionMeta[] }
  return data.sessions ?? []
}

export async function deleteSession(id: string): Promise<void> {
  await fetch(ourUrl(`/api/chat/sessions/${encodeURIComponent(id)}`), { method: 'DELETE' })
}

export async function renameSession(id: string, title: string): Promise<void> {
  await fetch(ourUrl(`/api/chat/sessions/${encodeURIComponent(id)}`), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

// Message types matching OV's Message interface
import type { Message } from '../-types/message'

export async function loadSessionMessages(
  sessionId: string,
  signal?: AbortSignal,
): Promise<Message[]> {
  const res = await fetch(ourUrl(`/api/chat/sessions/${encodeURIComponent(sessionId)}/messages`), {
    signal,
  })
  if (!res.ok) return []
  const data = (await res.json()) as { messages?: Array<Record<string, unknown>> }
  const raw = data.messages ?? []

  // Convert flat DB rows to OV Message format (with parts)
  return raw.map((m) => ({
    id: (m.id as string) || `msg_${Date.now().toString(36)}`,
    role: (m.role as 'user' | 'assistant') || 'user',
    parts: [{ type: 'text' as const, text: (m.content as string) || '' }],
    created_at: (m.created_at as string) || new Date().toISOString(),
  }))
}

export async function syncMessagesToStore(
  sessionId: string,
  messages: Message[],
): Promise<void> {
  // Convert OV Message[] to flat rows for our SQLite store
  const rows = messages.map((m) => {
    const textContent = m.parts
      .filter((p) => p.type === 'text')
      .map((p) => (p as { text: string }).text)
      .join('\n')
    return {
      id: m.id,
      role: m.role,
      content: textContent,
      created_at: m.created_at,
    }
  })
  await fetch(ourUrl(`/api/chat/sessions/${encodeURIComponent(sessionId)}/messages`), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rows),
  }).catch(() => {})
}

/** vikingbot session message add (for multi-turn context). */
export async function addMessage(
  _sessionId: string,
  _role: string,
  _content?: string,
  _parts?: string,
): Promise<void> {
  // vikingbot manages its own session context; this is a no-op.
}

export function serializeParts(_parts: unknown[]): string {
  return JSON.stringify(_parts)
}

/** Resolve relative chart paths against our FastAPI backend. */
export function resolveChartUrl(url: string | null): string | null {
  if (!url) return null
  if (/^https?:\/\//i.test(url)) return url
  return `${OUR_BASE}${url}`
}
