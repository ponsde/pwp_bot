import * as React from 'react'
import { Streamdown } from 'streamdown'
import { code } from '@streamdown/code'
import { cjk } from '@streamdown/cjk'
import hljs from 'highlight.js/lib/core'
import sql from 'highlight.js/lib/languages/sql'
import 'highlight.js/styles/github-dark.css'

import { cn } from '#/lib/utils'
import { resolveChartUrl } from '#/routes/sessions/-lib/api'

hljs.registerLanguage('sql', sql)

const plugins = { code, cjk }

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
        'prose-headings:font-semibold prose-headings:tracking-tight',
        'prose-h1:text-lg prose-h2:text-base prose-h3:text-sm',
        'prose-h1:mt-6 prose-h1:mb-3 prose-h2:mt-5 prose-h2:mb-2 prose-h3:mt-4 prose-h3:mb-2',
        'first:prose-headings:mt-0',
        'prose-p:leading-relaxed prose-p:my-2',
        'prose-a:text-primary prose-a:no-underline hover:prose-a:underline prose-a:font-medium',
        'prose-li:my-0.5',
        'prose-code:before:content-none prose-code:after:content-none',
        'prose-code:rounded prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:text-[13px] prose-code:font-normal',
        'prose-blockquote:border-l-primary/40 prose-blockquote:bg-muted/30 prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:not-italic',
        'prose-th:text-left prose-th:text-xs prose-th:font-semibold prose-th:uppercase prose-th:tracking-wider prose-th:text-muted-foreground',
        'prose-td:text-sm',
        'prose-hr:border-border/50',
        'prose-strong:font-semibold',
      )}
    >
      <Streamdown plugins={plugins} isAnimating={isStreaming}>
        {content}
      </Streamdown>
    </div>
  )
}

export function SqlBlock({ sql: sqlText }: { sql: string }) {
  const html = React.useMemo(() => {
    try {
      return hljs.highlight(sqlText, { language: 'sql' }).value
    } catch {
      return sqlText
    }
  }, [sqlText])
  return (
    <details className='my-3 rounded-lg border border-border/30 bg-muted/20' open>
      <summary className='flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs font-medium text-muted-foreground select-none'>
        <span>SQL</span>
      </summary>
      <pre className='overflow-x-auto border-t border-border/30 px-3 py-2 text-xs leading-relaxed'>
        <code className='hljs language-sql' dangerouslySetInnerHTML={{ __html: html }} />
      </pre>
    </details>
  )
}

export function ChartImage({ url }: { url: string | null }) {
  const resolved = resolveChartUrl(url)
  if (!resolved) return null
  return (
    <img
      src={resolved}
      alt='chart'
      className='mt-3 max-h-80 w-full rounded-md border object-contain'
    />
  )
}
