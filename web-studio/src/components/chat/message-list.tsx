import { memo, useCallback, useState } from 'react'
import { CheckIcon, CopyIcon, FileIcon, ImageIcon, PencilIcon, RefreshCwIcon, Trash2Icon, UserIcon, XIcon } from 'lucide-react'

import type { Message } from '#/routes/sessions/-types/message'
import type { StreamToolCall } from '#/routes/sessions/-types/chat'
import { MarkdownContent, ReasoningBlock, ToolCallBlock } from './message-parts'

// ---------------------------------------------------------------------------
// CopyButton
// ---------------------------------------------------------------------------

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    if (!text) return
    // Prefer Clipboard API (requires secure context), fall back to
    // legacy execCommand for http:// local dev where Clipboard is blocked.
    let ok = false
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text)
        ok = true
      }
    } catch (err) {
      console.warn('Clipboard API failed, falling back to execCommand', err)
    }
    if (!ok) {
      try {
        const ta = document.createElement('textarea')
        ta.value = text
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        ok = document.execCommand('copy')
        document.body.removeChild(ta)
      } catch (err) {
        console.error('Copy fallback failed', err)
      }
    }
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }
  }, [text])

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex size-6 items-center justify-center rounded-md text-muted-foreground/50 opacity-0 transition-all group-hover/msg:opacity-100 hover:bg-accent hover:text-accent-foreground"
      title="复制"
    >
      {copied ? <CheckIcon className="size-3" /> : <CopyIcon className="size-3" />}
    </button>
  )
}

function ActionBtn({ icon: Icon, title, onClick, variant }: {
  icon: React.ComponentType<{ className?: string }>; title: string; onClick: () => void; variant?: 'destructive'
}) {
  return (
    <button type="button" onClick={onClick} title={title}
      className={`inline-flex size-6 items-center justify-center rounded-md text-muted-foreground/50 ${variant === 'destructive' ? 'hover:bg-destructive/10 hover:text-destructive' : 'hover:bg-accent hover:text-accent-foreground'}`}>
      <Icon className="size-3" />
    </button>
  )
}

/** Extract all text content from a message's parts. */
function getTextFromParts(message: Message): string {
  return message.parts
    .filter((p) => p.type === 'text')
    .map((p) => (p as { text: string }).text)
    .join('\n')
}

/** Format relative time */
function formatRelativeTime(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diff = Math.max(0, now - then)
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}

// ---------------------------------------------------------------------------
// TypingIndicator
// ---------------------------------------------------------------------------

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="size-1.5 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:0ms]" />
      <span className="size-1.5 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:150ms]" />
      <span className="size-1.5 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:300ms]" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// BotAvatar — product brand avatar
// ---------------------------------------------------------------------------

function BotAvatar() {
  return (
    <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-primary/5 ring-1 ring-border/20" />
  )
}

// ---------------------------------------------------------------------------
// Attachment tag parsing
// ---------------------------------------------------------------------------

const ATTACHMENT_RE = /^\[uploaded_file:\s*(.+?),\s*temp_file_id:\s*(.+?)\]\n?/

function parseAttachment(text: string): {
  fileName: string
  tempFileId: string
  rest: string
} | null {
  const match = text.match(ATTACHMENT_RE)
  if (!match) return null
  return { fileName: match[1], tempFileId: match[2], rest: text.slice(match[0].length) }
}

function isImageFile(name: string): boolean {
  return /\.(jpg|jpeg|png|gif|webp|svg|bmp|ico)$/i.test(name)
}

// ---------------------------------------------------------------------------
// MessageList
// ---------------------------------------------------------------------------

interface MessageListProps {
  messages: Message[]
  attachmentPreviews?: Map<string, string>
  streaming?: {
    content: string
    toolCalls: StreamToolCall[]
    reasoning: string
    iteration: number
  }
  onDeleteMessage?: (id: string) => void
  onEditUserMessage?: (id: string, newContent: string) => void
  onEditAssistantMessage?: (id: string, newContent: string) => void
  onRetry?: () => void
  isStreaming?: boolean
}

export function MessageList({ messages, attachmentPreviews, streaming, onDeleteMessage, onEditUserMessage, onEditAssistantMessage, onRetry, isStreaming }: MessageListProps) {
  return (
    <>
      {messages.map((msg, idx) => {
        const prev = idx > 0 ? messages[idx - 1] : null
        const sameRole = prev?.role === msg.role
        const isLast = idx === messages.length - 1
        return msg.role === 'user' ? (
          <UserMessage key={msg.id} message={msg} compact={sameRole} attachmentPreviews={attachmentPreviews} onDelete={onDeleteMessage} onEdit={onEditUserMessage} disabled={isStreaming} />
        ) : (
          <AssistantMessage key={msg.id} message={msg} compact={sameRole} isLast={isLast} onDelete={onDeleteMessage} onEdit={onEditAssistantMessage} onRetry={onRetry} disabled={isStreaming} />
        )
      })}
      {streaming && <StreamingAssistantMessage {...streaming} />}
    </>
  )
}

// ---------------------------------------------------------------------------
// UserMessage
// ---------------------------------------------------------------------------

const UserMessage = memo(function UserMessage({
  message,
  compact,
  attachmentPreviews,
  onDelete,
  onEdit,
  disabled,
}: {
  message: Message
  compact?: boolean
  attachmentPreviews?: Map<string, string>
  onDelete?: (id: string) => void
  onEdit?: (id: string, newContent: string) => void
  disabled?: boolean
}) {
  const rawText = getTextFromParts(message)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(rawText)

  const handleSaveEdit = useCallback(() => {
    const trimmed = editText.trim()
    if (!trimmed) return
    setEditing(false)
    if (trimmed !== rawText) onEdit?.(message.id, trimmed)
  }, [editText, rawText, message.id, onEdit])

  const parsed = parseAttachment(rawText)
  const text = parsed ? parsed.rest : rawText
  const previewUrl = parsed ? attachmentPreviews?.get(parsed.tempFileId) : undefined

  return (
    <div className={`group/msg flex w-full max-w-3xl gap-3 justify-end ${compact ? 'mb-1.5' : 'mb-5'}`}>
      <div className="flex items-end gap-0.5 self-end opacity-0 transition-opacity group-hover/msg:opacity-100">
        <span className="text-[10px] text-muted-foreground/40 select-none mr-1">
          {formatRelativeTime(message.created_at)}
        </span>
        <CopyButton text={text || rawText} />
        {!disabled && onEdit && (
          <ActionBtn icon={PencilIcon} title="编辑" onClick={() => { setEditText(rawText); setEditing(true) }} />
        )}
        {!disabled && onDelete && (
          <ActionBtn icon={Trash2Icon} title="删除" onClick={() => onDelete(message.id)} variant="destructive" />
        )}
      </div>
      <div className="max-w-[75%] space-y-1.5">
        {parsed && (
          <div className="overflow-hidden rounded-2xl rounded-tr-sm border border-primary/20 bg-primary/90 shadow-sm">
            {previewUrl && isImageFile(parsed.fileName) ? (
              <img
                src={previewUrl}
                alt={parsed.fileName}
                className="max-h-64 w-full object-cover"
              />
            ) : null}
            <div className="flex items-center gap-2 px-3 py-2 text-xs text-primary-foreground/80">
              {isImageFile(parsed.fileName) ? (
                <ImageIcon className="size-3.5 shrink-0" />
              ) : (
                <FileIcon className="size-3.5 shrink-0" />
              )}
              <span className="min-w-0 flex-1 truncate">{parsed.fileName}</span>
            </div>
          </div>
        )}
        {editing ? (
          <div className="rounded-2xl rounded-tr-sm bg-primary/90 px-3 py-2 shadow-sm">
            <textarea autoFocus value={editText} onChange={(e) => setEditText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSaveEdit() } if (e.key === 'Escape') setEditing(false) }}
              className="w-full min-h-[2.5rem] resize-none bg-transparent text-sm text-primary-foreground focus:outline-none" rows={2} />
            <div className="flex justify-end gap-1 mt-1">
              <button type="button" onClick={() => setEditing(false)} className="inline-flex size-6 items-center justify-center rounded text-primary-foreground/60 hover:text-primary-foreground"><XIcon className="size-3.5" /></button>
              <button type="button" onClick={handleSaveEdit} className="inline-flex size-6 items-center justify-center rounded text-primary-foreground/60 hover:text-primary-foreground"><CheckIcon className="size-3.5" /></button>
            </div>
          </div>
        ) : text ? (
          <div className="rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground whitespace-pre-wrap shadow-sm">
            {text}
          </div>
        ) : null}
      </div>
      {!compact && (
        <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <UserIcon className="size-3.5 text-primary" />
        </div>
      )}
      {compact && <div className="w-7 shrink-0" />}
    </div>
  )
})

// ---------------------------------------------------------------------------
// AssistantMessage (completed)
// ---------------------------------------------------------------------------

const AssistantMessage = memo(function AssistantMessage({
  message,
  compact,
  isLast,
  onDelete,
  onEdit,
  onRetry,
  disabled,
}: {
  message: Message
  compact?: boolean
  isLast?: boolean
  onDelete?: (id: string) => void
  onEdit?: (id: string, newContent: string) => void
  onRetry?: () => void
  disabled?: boolean
}) {
  const textContent = getTextFromParts(message)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(textContent)

  const handleSaveEdit = useCallback(() => {
    const trimmed = editText.trim()
    if (!trimmed) return
    setEditing(false)
    if (trimmed !== textContent) onEdit?.(message.id, trimmed)
  }, [editText, textContent, message.id, onEdit])

  return (
    <div className={`group/msg flex w-full max-w-3xl gap-3 items-start ${compact ? 'mb-1.5' : 'mb-5'}`}>
      {!compact ? <BotAvatar /> : <div className="w-7 shrink-0" />}
      <div className="max-w-full min-w-0 flex-1 rounded-2xl rounded-tl-sm bg-background/95 px-4 py-3 text-sm shadow-sm ring-1 ring-border/30">
        {message.parts.map((part, i) => {
          switch (part.type) {
            case 'text':
              return editing ? null : <MarkdownContent key={i} content={part.text} />
            case 'tool':
              return (
                <ToolCallBlock
                  key={i}
                  toolName={part.tool_name}
                  args={part.tool_input}
                  result={part.tool_output}
                  isError={part.tool_status === 'error'}
                  isRunning={false}
                />
              )
            case 'context':
              return null
          }
        })}
        {editing && (
          <div>
            <textarea autoFocus value={editText} onChange={(e) => setEditText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Escape') setEditing(false) }}
              className="w-full min-h-[4rem] resize-y rounded-md border bg-background p-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring" rows={4} />
            <div className="flex justify-end gap-1 mt-2">
              <button type="button" onClick={() => setEditing(false)} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent"><XIcon className="size-3" /> 取消</button>
              <button type="button" onClick={handleSaveEdit} className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90"><CheckIcon className="size-3" /> 保存</button>
            </div>
          </div>
        )}
      </div>
      <div className="flex flex-col items-center gap-0.5 self-end opacity-0 transition-opacity group-hover/msg:opacity-100">
        <CopyButton text={textContent} />
        {!disabled && onEdit && (
          <ActionBtn icon={PencilIcon} title="编辑" onClick={() => { setEditText(textContent); setEditing(true) }} />
        )}
        {!disabled && isLast && onRetry && (
          <ActionBtn icon={RefreshCwIcon} title="重试" onClick={onRetry} />
        )}
        {!disabled && onDelete && (
          <ActionBtn icon={Trash2Icon} title="删除" onClick={() => onDelete(message.id)} variant="destructive" />
        )}
        <span className="text-[10px] text-muted-foreground/40 select-none">
          {formatRelativeTime(message.created_at)}
        </span>
      </div>
    </div>
  )
})

// ---------------------------------------------------------------------------
// StreamingAssistantMessage (in-flight)
// ---------------------------------------------------------------------------

function StreamingAssistantMessage({
  content,
  toolCalls,
  reasoning,
  iteration,
}: {
  content: string
  toolCalls: StreamToolCall[]
  reasoning: string
  iteration: number
}) {
  const hasContent = content || toolCalls.length > 0 || reasoning

  return (
    <div className="mb-5 flex w-full max-w-3xl gap-3 items-start">
      <BotAvatar />
      <div className="max-w-full min-w-0 flex-1 rounded-2xl rounded-tl-sm bg-background/95 px-4 py-3 text-sm shadow-sm ring-1 ring-border/30">
        {iteration > 1 && (
          <div className="mb-2">
            <span className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-medium text-primary">
              第 {iteration} 轮
            </span>
          </div>
        )}

        <ReasoningBlock reasoning={reasoning} isRunning />

        {toolCalls.map((tc, i) => {
          let args: Record<string, unknown> = {}
          try {
            args = JSON.parse(tc.arguments) as Record<string, unknown>
          } catch {
            if (tc.arguments) args = { raw: tc.arguments }
          }
          return (
            <ToolCallBlock
              key={i}
              toolName={tc.name}
              args={args}
              result={tc.result}
              isRunning={!tc.result}
            />
          )
        })}

        {content ? (
          <MarkdownContent content={content} isStreaming />
        ) : !hasContent ? (
          <TypingIndicator />
        ) : null}
      </div>
    </div>
  )
}
