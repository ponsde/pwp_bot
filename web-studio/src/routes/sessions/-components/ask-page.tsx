import { useEffect, useState } from 'react'

import { Thread } from '#/components/chat/thread'
import { Route as SessionsRoute } from '#/routes/sessions/route'

function generateSessionId(): string {
  return `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

export function AskPage() {
  const search = SessionsRoute.useSearch()
  const urlSessionId = search.s
  const urlNew = search.new

  // When ?new=true, generate a fresh session id so Thread remounts.
  // When ?s=<id>, use that. Otherwise fall back to a stable default.
  const [draftId, setDraftId] = useState(generateSessionId)

  // Each time ?new flips to true, regenerate draft so clicking + again works.
  useEffect(() => {
    if (urlNew) setDraftId(generateSessionId())
  }, [urlNew])

  const sessionId = urlSessionId || draftId

  return (
    <div className='flex h-full w-full'>
      <Thread key={sessionId} sessionId={sessionId} />
    </div>
  )
}
