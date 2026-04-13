import '#/i18n'
// taidi-overlay: purge any stale baseUrl from a previous visit to a
// different OV host before AppConnectionProvider reads it. Embedded OV is
// always same-origin; a lingering http://127.0.0.1:1933 (or similar) from
// upstream-dev localStorage makes /health hang and the top-bar badge stuck
// on "Detecting".
try {
  const raw = window.localStorage.getItem('ov_console_connection')
  if (raw) {
    const parsed = JSON.parse(raw) as { baseUrl?: string }
    const base = parsed?.baseUrl
    if (base && !/^\/?$/.test(base) && !base.startsWith('/')) {
      window.localStorage.removeItem('ov_console_connection')
    }
  }
} catch {
  window.localStorage.removeItem('ov_console_connection')
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
