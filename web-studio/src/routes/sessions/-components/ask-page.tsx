import * as React from 'react'
import { SendHorizonalIcon, SparklesIcon } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import hljs from 'highlight.js/lib/core'
import sql from 'highlight.js/lib/languages/sql'
import 'highlight.js/styles/github-dark.css'

import { Button } from '#/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '#/components/ui/card'
import { Textarea } from '#/components/ui/textarea'
import { postAsk, resolveChartUrl } from '../-lib/api'
import type { AskResponse } from '../-lib/api'

hljs.registerLanguage('sql', sql)

type AskTurn = {
  id: string
  question: string
  response?: AskResponse
  pending?: boolean
  error?: string
}

export function AskPage() {
  const [input, setInput] = React.useState('')
  const [turns, setTurns] = React.useState<AskTurn[]>([])
  const [pending, setPending] = React.useState(false)
  const sessionIdRef = React.useRef<string | undefined>(undefined)
  const scrollRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns])

  const submit = async () => {
    const question = input.trim()
    if (!question || pending) return
    const id = crypto.randomUUID()
    setTurns((prev) => [...prev, { id, question, pending: true }])
    setInput('')
    setPending(true)
    try {
      const response = await postAsk({ question, session_id: sessionIdRef.current })
      sessionIdRef.current = response.session_id
      setTurns((prev) =>
        prev.map((turn) => (turn.id === id ? { ...turn, pending: false, response } : turn)),
      )
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setTurns((prev) =>
        prev.map((turn) => (turn.id === id ? { ...turn, pending: false, error: message } : turn)),
      )
    } finally {
      setPending(false)
    }
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      void submit()
    }
  }

  return (
    <div className='mx-auto flex h-full w-full max-w-4xl flex-col gap-4 p-6'>
      <header className='flex items-center gap-3'>
        <SparklesIcon className='size-5 text-primary' />
        <h1 className='text-lg font-semibold'>财报智能问数</h1>
      </header>

      <div ref={scrollRef} className='flex-1 overflow-y-auto pr-1'>
        {turns.length === 0 ? (
          <div className='flex h-full items-center justify-center text-sm text-muted-foreground'>
            输入问题开始，例如"华润三九 2024 年净利润同比是多少"。
          </div>
        ) : (
          <div className='flex flex-col gap-4'>
            {turns.map((turn) => (
              <AskTurnView key={turn.id} turn={turn} />
            ))}
          </div>
        )}
      </div>

      <div className='rounded-lg border bg-background p-3'>
        <Textarea
          value={input}
          placeholder='请输入你的财报问题（⌘/Ctrl+Enter 发送）'
          rows={2}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={onKeyDown}
          className='mb-2 resize-none border-none bg-transparent p-0 shadow-none focus-visible:ring-0'
        />
        <div className='flex justify-end'>
          <Button size='sm' onClick={() => void submit()} disabled={!input.trim() || pending}>
            <SendHorizonalIcon className='mr-1 size-4' />
            发送
          </Button>
        </div>
      </div>
    </div>
  )
}

function AskTurnView({ turn }: { turn: AskTurn }) {
  const chartUrl = resolveChartUrl(turn.response?.chart_url ?? null)
  return (
    <div className='flex flex-col gap-2'>
      <Card className='self-end border-primary/20 bg-primary/5'>
        <CardContent className='py-3 text-sm'>{turn.question}</CardContent>
      </Card>
      <Card>
        <CardHeader className='pb-2'>
          <CardTitle className='text-xs font-medium text-muted-foreground'>
            {turn.response?.needs_clarification ? '需要补充' : '回答'}
          </CardTitle>
        </CardHeader>
        <CardContent className='space-y-3 text-sm'>
          {turn.pending ? (
            <span className='text-muted-foreground'>思考中…</span>
          ) : turn.error ? (
            <span className='text-destructive'>{turn.error}</span>
          ) : (
            <div className='prose prose-sm dark:prose-invert max-w-none'>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {turn.response?.content ?? ''}
              </ReactMarkdown>
            </div>
          )}
          {turn.response?.sql ? <SqlBlock sql={turn.response.sql} /> : null}
          {chartUrl ? (
            <img
              src={chartUrl}
              alt='chart'
              className='max-h-80 w-full rounded-md border object-contain'
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

function SqlBlock({ sql: sqlText }: { sql: string }) {
  const html = React.useMemo(() => {
    try {
      return hljs.highlight(sqlText, { language: 'sql' }).value
    } catch {
      return sqlText
    }
  }, [sqlText])
  return (
    <pre className='overflow-x-auto rounded-md bg-muted p-3 text-xs'>
      <code className='hljs language-sql' dangerouslySetInnerHTML={{ __html: html }} />
    </pre>
  )
}
