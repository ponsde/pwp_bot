import { useCallback, useEffect, useRef } from 'react'
import { SparklesIcon } from 'lucide-react'

import { useAskChat } from '#/routes/sessions/-hooks/use-ask-chat'
import { Composer } from './composer'
import { MessageList } from './message-list'

export function Thread() {
  const chat = useAskChat()
  const isStreaming = chat.status === 'streaming'

  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const isNearBottomRef = useRef(true)
  const scrollRafRef = useRef(0)

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    isNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100
  }, [])

  useEffect(() => {
    if (!isNearBottomRef.current) return
    cancelAnimationFrame(scrollRafRef.current)
    scrollRafRef.current = requestAnimationFrame(() => {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    })
  }, [chat.messages.length, chat.streamingStatus, chat.streamingSql])

  const isEmpty = chat.messages.length === 0 && !isStreaming

  return (
    <div className='relative flex h-full flex-col'>
      <div className='relative z-10 flex h-12 items-center border-b border-border/50 bg-background/95 px-6'>
        <SparklesIcon className='size-4 text-primary mr-2' />
        <h2 className='text-sm font-medium truncate text-foreground'>财报智能问数</h2>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className='relative z-10 flex flex-1 flex-col items-center overflow-y-auto px-4 pt-12 pb-24'
      >
        {isEmpty ? (
          <ThreadEmpty />
        ) : (
          <MessageList
            messages={chat.messages}
            streaming={
              isStreaming ? { status: chat.streamingStatus, sql: chat.streamingSql } : undefined
            }
          />
        )}
        <div ref={bottomRef} />
      </div>

      <div className='relative z-10'>
        <Composer
          onSend={chat.send}
          onCancel={chat.abort}
          isStreaming={isStreaming}
          placeholder='请输入你的财报问题（Enter 发送，Shift+Enter 换行）'
        />
      </div>
    </div>
  )
}

function ThreadEmpty() {
  return (
    <div className='flex grow flex-col items-center justify-center gap-3'>
      <div className='flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 ring-1 ring-primary/10'>
        <SparklesIcon className='size-7 text-primary/70' />
      </div>
      <div className='text-center'>
        <h3 className='text-base font-medium text-foreground'>财报智能问数</h3>
        <p className='mt-1 text-sm text-muted-foreground'>
          输入问题开始，例如"华润三九 2024 年净利润同比是多少"。
        </p>
      </div>
    </div>
  )
}
