import { memo, useCallback, useState } from 'react'
import { CheckIcon, CopyIcon, SparklesIcon, UserIcon } from 'lucide-react'

import type {
  AssistantChatMessage,
  ChatMessage,
  UserChatMessage,
} from '#/routes/sessions/-hooks/use-ask-chat'
import { ChartImage, MarkdownContent, SqlBlock } from './message-parts'

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = useCallback(async () => {
    if (!text) return
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [text])
  return (
    <button
      type='button'
      onClick={handleCopy}
      className='inline-flex size-6 items-center justify-center rounded-md text-muted-foreground/50 opacity-0 transition-all group-hover/msg:opacity-100 hover:bg-accent hover:text-accent-foreground'
      title='复制'
    >
      {copied ? <CheckIcon className='size-3' /> : <CopyIcon className='size-3' />}
    </button>
  )
}

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

function TypingIndicator() {
  return (
    <div className='flex items-center gap-1 py-1'>
      <span className='size-1.5 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:0ms]' />
      <span className='size-1.5 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:150ms]' />
      <span className='size-1.5 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:300ms]' />
    </div>
  )
}

function BotAvatar() {
  return (
    <div className='flex size-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-primary/5 ring-1 ring-primary/15'>
      <SparklesIcon className='size-3.5 text-primary' />
    </div>
  )
}

interface MessageListProps {
  messages: ChatMessage[]
  streaming?: {
    status: string
    sql: string
  }
}

export function MessageList({ messages, streaming }: MessageListProps) {
  return (
    <>
      {messages.map((msg, idx) => {
        const prev = idx > 0 ? messages[idx - 1] : null
        const sameRole = prev?.role === msg.role
        return msg.role === 'user' ? (
          <UserMessage key={msg.id} message={msg} compact={sameRole} />
        ) : (
          <AssistantMessage key={msg.id} message={msg} compact={sameRole} />
        )
      })}
      {streaming && <StreamingAssistantMessage status={streaming.status} sql={streaming.sql} />}
    </>
  )
}

const UserMessage = memo(function UserMessage({
  message,
  compact,
}: {
  message: UserChatMessage
  compact?: boolean
}) {
  return (
    <div
      className={`group/msg flex w-full max-w-3xl gap-3 justify-end ${compact ? 'mb-1.5' : 'mb-5'}`}
    >
      <div className='flex items-end gap-1.5 self-end'>
        <span className='text-[10px] text-muted-foreground/40 opacity-0 transition-opacity group-hover/msg:opacity-100 select-none'>
          {formatRelativeTime(message.createdAt)}
        </span>
        <CopyButton text={message.content} />
      </div>
      <div className='max-w-[75%] space-y-1.5'>
        <div className='rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground whitespace-pre-wrap shadow-sm'>
          {message.content}
        </div>
      </div>
      {!compact ? (
        <div className='flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10'>
          <UserIcon className='size-3.5 text-primary' />
        </div>
      ) : (
        <div className='w-7 shrink-0' />
      )}
    </div>
  )
})

const AssistantMessage = memo(function AssistantMessage({
  message,
  compact,
}: {
  message: AssistantChatMessage
  compact?: boolean
}) {
  return (
    <div
      className={`group/msg flex w-full max-w-3xl gap-3 items-start ${compact ? 'mb-1.5' : 'mb-5'}`}
    >
      {!compact ? <BotAvatar /> : <div className='w-7 shrink-0' />}
      <div className='max-w-full min-w-0 flex-1 rounded-2xl rounded-tl-sm bg-background/95 px-4 py-3 text-sm shadow-sm ring-1 ring-border/30'>
        {message.needsClarification && (
          <div className='mb-2'>
            <span className='inline-flex items-center rounded-full bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-400'>
              需要补充信息
            </span>
          </div>
        )}
        <MarkdownContent content={message.content} />
        {message.sql ? <SqlBlock sql={message.sql} /> : null}
        <ChartImage url={message.chartUrl} />
      </div>
      <div className='flex items-end gap-1.5 self-end'>
        <CopyButton text={message.content} />
        <span className='text-[10px] text-muted-foreground/40 opacity-0 transition-opacity group-hover/msg:opacity-100 select-none'>
          {formatRelativeTime(message.createdAt)}
        </span>
      </div>
    </div>
  )
})

function StreamingAssistantMessage({ status, sql }: { status: string; sql: string }) {
  return (
    <div className='mb-5 flex w-full max-w-3xl gap-3 items-start'>
      <BotAvatar />
      <div className='max-w-full min-w-0 flex-1 rounded-2xl rounded-tl-sm bg-background/95 px-4 py-3 text-sm shadow-sm ring-1 ring-border/30'>
        {status ? (
          <div className='flex items-center gap-2 text-xs text-muted-foreground'>
            <TypingIndicator />
            <span>{status}</span>
          </div>
        ) : (
          <TypingIndicator />
        )}
        {sql ? <SqlBlock sql={sql} /> : null}
      </div>
    </div>
  )
}
