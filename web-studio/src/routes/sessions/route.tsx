import { createFileRoute } from '@tanstack/react-router'

import { AskPage } from './-components/ask-page'

export const Route = createFileRoute('/sessions')({
  component: AskPage,
})
