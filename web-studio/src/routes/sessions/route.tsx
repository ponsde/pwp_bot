import { createFileRoute } from '@tanstack/react-router'

import { AskPage } from './-components/ask-page'

type SessionsSearch = {
  s?: string
  new?: boolean
}

export const Route = createFileRoute('/sessions')({
  component: AskPage,
  validateSearch: (raw: Record<string, unknown>): SessionsSearch => ({
    s: typeof raw.s === 'string' && raw.s.length > 0 ? raw.s : undefined,
    new: raw.new === true || raw.new === 'true' || raw.new === 1 || raw.new === '1',
  }),
})
