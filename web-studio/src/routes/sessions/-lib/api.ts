const ENV_BASE_URL =
  typeof import.meta.env.VITE_API_BASE_URL === 'string'
    ? import.meta.env.VITE_API_BASE_URL.trim().replace(/\/+$/, '')
    : ''

function resolveUrl(path: string): string {
  return `${ENV_BASE_URL}${path}`
}

export type AskRow = Record<string, unknown>

export type AskResponse = {
  session_id: string
  content: string
  sql: string | null
  rows: Array<AskRow>
  chart_url: string | null
  chart_type: string | null
  needs_clarification: boolean
  error: string | null
}

export type AskRequest = {
  question: string
  session_id?: string
}

export async function postAsk(req: AskRequest, signal?: AbortSignal): Promise<AskResponse> {
  const res = await fetch(resolveUrl('/api/ask'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`ask failed (${res.status}): ${text || res.statusText}`)
  }
  return (await res.json()) as AskResponse
}

export type StreamEvent =
  | { type: 'status'; payload: { stage: string; message: string; route?: string } }
  | { type: 'sql'; payload: { sql: string } }
  | { type: 'done'; payload: AskResponse }
  | { type: 'error'; payload: { message: string } }

/** POST /api/ask/stream and yield SSE events as they arrive. */
export async function* streamAsk(
  req: AskRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent, void, void> {
  const res = await fetch(resolveUrl('/api/ask/stream'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(req),
    signal,
  })
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '')
    throw new Error(`stream failed (${res.status}): ${text || res.statusText}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let sep: number
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        const parsed = parseSseBlock(raw)
        if (parsed) yield parsed
      }
    }
  } finally {
    reader.releaseLock()
  }
}

function parseSseBlock(raw: string): StreamEvent | null {
  let event: string | null = null
  let data: string | null = null
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data = (data ?? '') + line.slice(5).trim()
  }
  if (!event || data === null) return null
  try {
    const payload = JSON.parse(data) as Record<string, unknown>
    return { type: event as StreamEvent['type'], payload } as StreamEvent
  } catch {
    return null
  }
}

/** Resolve relative chart paths (e.g. "/charts/foo.jpg") against the API base. */
export function resolveChartUrl(url: string | null): string | null {
  if (!url) return null
  if (/^https?:\/\//i.test(url)) return url
  return resolveUrl(url)
}
