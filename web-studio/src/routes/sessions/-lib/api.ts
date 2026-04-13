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

/** Resolve relative chart paths (e.g. "/charts/foo.jpg") against the API base. */
export function resolveChartUrl(url: string | null): string | null {
  if (!url) return null
  if (/^https?:\/\//i.test(url)) return url
  return resolveUrl(url)
}
