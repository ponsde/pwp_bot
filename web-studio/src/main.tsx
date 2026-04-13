import '#/i18n'
// taidi-overlay: seed AppConnectionProvider's persisted connection so its
// baseUrl is the current origin (real URL), not the Vite-baked "/" which
// normalizeBaseUrl strips to an empty string — and an empty baseUrl short-
// circuits detectServerMode straight to "offline". Also evicts any legacy
// value pointing at someone else's OV dev host.
try {
  const key = 'ov_console_connection'
  const desired = window.location.origin
  const raw = window.localStorage.getItem(key)
  const parsed: Record<string, unknown> | null = raw ? JSON.parse(raw) : null
  const current = typeof parsed?.baseUrl === 'string' ? parsed.baseUrl.trim() : ''
  const isStale =
    !current ||
    current === '/' ||
    /^https?:\/\/127\.0\.0\.1/.test(current) ||
    /^https?:\/\/localhost/.test(current)
  if (isStale) {
    window.localStorage.setItem(
      key,
      JSON.stringify({ ...(parsed ?? {}), baseUrl: desired }),
    )
  }
} catch {
  /* ignore malformed localStorage */
}
import ReactDOM from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { ThemeProvider } from 'next-themes'
import { routeTree } from './routeTree.gen'
import { TooltipProvider } from './components/ui/tooltip'
import { queryClient } from './lib/query-client'

const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  scrollRestoration: true,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

const rootElement = document.getElementById('app')!

if (!rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement)
  root.render(
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <RouterProvider router={router} />
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>,
  )
}
