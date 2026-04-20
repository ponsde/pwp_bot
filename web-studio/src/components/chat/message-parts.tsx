import { Streamdown } from 'streamdown'
import { code } from '@streamdown/code'
import { cjk } from '@streamdown/cjk'
import {
  CheckCircle2Icon,
  CircleAlertIcon,
  LoaderIcon,
  WrenchIcon,
} from 'lucide-react'

import { cn } from '#/lib/utils'

const plugins = { code, cjk }

// ---------------------------------------------------------------------------
// MarkdownContent
// ---------------------------------------------------------------------------

interface MarkdownContentProps {
  content: string
  isStreaming?: boolean
}

export function MarkdownContent({ content, isStreaming }: MarkdownContentProps) {
  if (!content) return null

  return (
    <div
      className={cn(
        'prose prose-sm dark:prose-invert max-w-none',
        // Headings
        'prose-headings:font-semibold prose-headings:tracking-tight',
        'prose-h1:text-lg prose-h2:text-base prose-h3:text-sm',
        'prose-h1:mt-6 prose-h1:mb-3 prose-h2:mt-5 prose-h2:mb-2 prose-h3:mt-4 prose-h3:mb-2',
        'first:prose-headings:mt-0',
        // Paragraphs
        'prose-p:leading-relaxed prose-p:my-2',
        // Links
        'prose-a:text-primary prose-a:no-underline hover:prose-a:underline prose-a:font-medium',
        // Lists
        'prose-li:my-0.5',
        // Code inline
        'prose-code:before:content-none prose-code:after:content-none',
        'prose-code:rounded prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:text-[13px] prose-code:font-normal',
        // Blockquote
        'prose-blockquote:border-l-primary/40 prose-blockquote:bg-muted/30 prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:not-italic',
        // Tables
        'prose-th:text-left prose-th:text-xs prose-th:font-semibold prose-th:uppercase prose-th:tracking-wider prose-th:text-muted-foreground',
        'prose-td:text-sm',
        // HR
        'prose-hr:border-border/50',
        // Strong
        'prose-strong:font-semibold',
      )}
    >
      <Streamdown plugins={plugins} isAnimating={isStreaming}>
        {content}
      </Streamdown>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ReasoningBlock
// ---------------------------------------------------------------------------

interface ReasoningBlockProps {
  reasoning: string
  isRunning: boolean
}

export function ReasoningBlock({ reasoning, isRunning }: ReasoningBlockProps) {
  if (!reasoning) return null

  return (
    <details className="mb-3 rounded-lg border border-border/30 bg-muted/20" open={isRunning}>
      <summary className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs font-medium text-muted-foreground select-none">
        {isRunning && <LoaderIcon className="size-3 animate-spin" />}
        <span>{isRunning ? '思考中...' : '思考过程'}</span>
      </summary>
      <div className="border-t border-border/30 px-3 py-2 text-xs text-muted-foreground/80 leading-relaxed whitespace-pre-wrap">
        {reasoning}
      </div>
    </details>
  )
}

// ---------------------------------------------------------------------------
// ToolCallBlock
// ---------------------------------------------------------------------------

interface ToolCallBlockProps {
  toolName: string
  args?: Record<string, unknown>
  result?: string
  isError?: boolean
  isRunning: boolean
}

export function ToolCallBlock({ toolName, args, result, isError, isRunning }: ToolCallBlockProps) {
  const refs = !isError && result ? extractReferences(result) : []
  const hasRefs = refs.length > 0
  return (
    <details className="my-2 rounded-lg border border-border/30 bg-muted/20" open={hasRefs}>
      <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 text-xs select-none">
        <ToolStatusIcon isRunning={isRunning} isError={isError} />
        <WrenchIcon className="size-3 text-muted-foreground/60" />
        <span className="font-mono font-medium text-foreground/80">{toolName}</span>
        {hasRefs && (
          <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
            {refs.length} 条引用
          </span>
        )}
        <span className="ml-auto text-muted-foreground/60 text-[11px]">
          {isRunning ? '执行中...' : isError ? '失败' : '完成'}
        </span>
      </summary>
      <div className="space-y-2 border-t border-border/30 px-3 py-2">
        {args && Object.keys(args).length > 0 && (
          <div>
            <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/50">
              输入
            </div>
            <pre className="overflow-x-auto rounded-md bg-muted/50 p-2 text-xs leading-relaxed">
              {JSON.stringify(args, null, 2)}
            </pre>
          </div>
        )}
        {hasRefs && (
          <div>
            <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/50">
              参考文献 · {refs.length} 条
            </div>
            <ReferencesList refs={refs} />
          </div>
        )}
        {result !== undefined && (
          <div>
            <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/50">
              原始返回
            </div>
            <pre
              className={cn(
                'max-h-48 overflow-x-auto overflow-y-auto rounded-md p-2 text-xs leading-relaxed',
                isError ? 'bg-destructive/10 text-destructive' : 'bg-muted/50',
              )}
            >
              {result}
            </pre>
          </div>
        )}
      </div>
    </details>
  )
}

// ---------------------------------------------------------------------------
// References extraction — detects RAG-style references in tool output
// ---------------------------------------------------------------------------

interface Ref {
  paper_path?: string
  text?: string
  paper_image?: string
  title?: string
}

const REF_KEYS = ['references', 'resources', 'memories', 'sources', 'matches', 'results'] as const

function extractReferences(raw: string): Ref[] {
  if (!raw || raw.length > 200_000) return []
  // Try plain JSON first; openviking tools return a Python repr dict
  // ({'key': 'val', 'abstract': "val with 'apostrophe'"}). Naive s/'/"/g
  // corrupts embedded apostrophes; use a state-machine repr→JSON converter.
  let obj: unknown = null
  try {
    obj = JSON.parse(raw)
  } catch {
    try {
      obj = JSON.parse(pyReprToJson(raw))
    } catch {
      return []
    }
  }
  if (!obj || typeof obj !== 'object') return []
  const root = obj as Record<string, unknown>
  for (const key of REF_KEYS) {
    const arr = root[key]
    if (Array.isArray(arr)) return coerceRefs(arr)
  }
  // Nested shapes: e.g. {"data": {"resources": [...]}} or {"result": {...}}
  for (const v of Object.values(root)) {
    if (v && typeof v === 'object') {
      const inner = v as Record<string, unknown>
      for (const key of REF_KEYS) {
        const arr = inner[key]
        if (Array.isArray(arr)) return coerceRefs(arr)
      }
    }
  }
  return []
}

/**
 * Convert Python dict/list repr to JSON. Walks char-by-char tracking
 * single- vs double-quoted string state so apostrophes inside values
 * like "User's memory" survive. Also normalizes Python literals
 * True/False/None → true/false/null.
 */
function pyReprToJson(src: string): string {
  let out = ''
  let i = 0
  const n = src.length
  let inSingle = false
  let inDouble = false
  while (i < n) {
    const c = src[i]
    // Preserve escape sequences verbatim inside any string
    if ((inSingle || inDouble) && c === '\\' && i + 1 < n) {
      out += c + src[i + 1]
      i += 2
      continue
    }
    if (!inDouble && !inSingle) {
      // Outside any string — recognize Python literals
      if (c === "'") { inSingle = true; out += '"' }
      else if (c === '"') { inDouble = true; out += '"' }
      else if (src.startsWith('True', i)) { out += 'true'; i += 4; continue }
      else if (src.startsWith('False', i)) { out += 'false'; i += 5; continue }
      else if (src.startsWith('None', i)) { out += 'null'; i += 4; continue }
      else out += c
    } else if (inSingle) {
      // Single-quoted string — close, but pre-escape any inner " as \"
      if (c === "'") { inSingle = false; out += '"' }
      else if (c === '"') { out += '\\"' }
      else out += c
    } else {
      // Double-quoted string — normal JSON rules, but keep apostrophes raw
      if (c === '"') { inDouble = false; out += '"' }
      else out += c
    }
    i++
  }
  return out
}


function coerceRefs(items: unknown[]): Ref[] {
  const out: Ref[] = []
  for (const item of items) {
    if (typeof item === 'string' && item.trim()) {
      // Plain string (e.g. mcp_fin_query sources array: "数据来源: income_sheet")
      out.push({ text: item.trim() })
      continue
    }
    if (!item || typeof item !== 'object') continue
    const it = item as Record<string, unknown>
    const pp = pickStr(it, ['paper_path', 'path', 'file', 'source', 'uri'])
    const text = pickStr(it, ['text', 'content', 'snippet', 'excerpt', 'summary'])
    const paper_image = pickStr(it, ['paper_image', 'image', 'img'])
    const title = pickStr(it, ['title', 'name'])
    if (pp || text || title) out.push({ paper_path: pp, text, paper_image, title })
  }
  return out
}

function pickStr(obj: Record<string, unknown>, keys: string[]): string | undefined {
  for (const k of keys) {
    const v = obj[k]
    if (typeof v === 'string' && v.trim().length > 0) return v
  }
  return undefined
}

function ReferencesList({ refs }: { refs: Ref[] }) {
  return (
    <ul className="space-y-1.5">
      {refs.slice(0, 12).map((r, i) => {
        const href = paperHref(r.paper_path)
        const inner = (
          <div className="flex items-start gap-2">
            <span className="mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full bg-primary/15 text-[10px] font-semibold text-primary">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-medium text-foreground/90">
                {shortPath(r.paper_path) || r.title || '（未命名）'}
              </div>
              {r.text && (
                <div className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                  {r.text}
                </div>
              )}
            </div>
          </div>
        )
        return (
          <li key={i} className="rounded-md border border-border/40 bg-background/60">
            {href ? (
              <a
                href={href}
                className="block px-2.5 py-1.5 transition-colors hover:bg-muted/50 cursor-pointer"
                onClick={(e) => {
                  // TanStack Router installs a global click interceptor for
                  // in-app links; force a hard navigation for static /papers
                  // URLs so the browser opens the PDF natively.
                  if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return
                  e.preventDefault()
                  window.location.href = href
                }}
              >
                {inner}
              </a>
            ) : (
              <div className="px-2.5 py-1.5">{inner}</div>
            )}
          </li>
        )
      })}
      {refs.length > 12 && (
        <li className="pl-6 text-[11px] text-muted-foreground/70">
          …还有 {refs.length - 12} 条
        </li>
      )}
    </ul>
  )
}

/**
 * Build a same-origin URL for a paper_path like "./附件5：研报数据/.../x.pdf".
 * Returns null when the ref has no resolvable path (e.g. viking:// internal
 * URI or a plain string source).
 */
function paperHref(p?: string): string | null {
  if (!p) return null
  const trimmed = p.trim()
  if (!trimmed || trimmed.startsWith('viking://')) return null
  // Strip leading ./ and encode each segment so Chinese chars work in href.
  const rel = trimmed.replace(/^\.\//, '')
  return '/papers/' + rel.split('/').map(encodeURIComponent).join('/')
}

function shortPath(p?: string): string | undefined {
  if (!p) return undefined
  // Keep just the filename for display
  const clean = p.replace(/^viking:\/\/[^/]*\//, '').replace(/^\.\//, '')
  const parts = clean.split('/')
  return parts[parts.length - 1] || clean
}

function ToolStatusIcon({ isRunning, isError }: { isRunning: boolean; isError?: boolean }) {
  if (isRunning) return <LoaderIcon className="size-3 animate-spin text-muted-foreground" />
  if (isError) return <CircleAlertIcon className="size-3 text-destructive" />
  return <CheckCircle2Icon className="size-3 text-primary/70" />
}
