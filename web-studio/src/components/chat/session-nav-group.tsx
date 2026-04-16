import { Link, useNavigate, useRouterState } from '@tanstack/react-router'
import { BlocksIcon, ChevronRightIcon, PlusIcon, Trash2Icon } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '#/components/ui/collapsible'
import {
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from '#/components/ui/sidebar'
import { useSessions } from '#/routes/sessions/-hooks/use-sessions'

export function SessionNavGroup() {
  const { t } = useTranslation('appShell')
  const navigate = useNavigate()
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const search = useRouterState({ select: (s) => s.location.search as { s?: string } })
  const activeId = search?.s as string | undefined

  const { sessions, remove } = useSessions()

  const isActiveRoute = pathname === '/sessions' || pathname.startsWith('/sessions/')

  const handleCreate = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    void navigate({ to: '/sessions', search: { new: true } })
  }

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm('删除此会话？')) return
    await remove(sessionId)
    if (activeId === sessionId) {
      void navigate({ to: '/sessions', search: { new: true } })
    }
  }

  const title = t('navigation.sessions.title')

  return (
    <Collapsible defaultOpen className='group/collapsible'>
      <SidebarMenuItem>
        <div className='flex items-center'>
          <CollapsibleTrigger
            render={
              <SidebarMenuButton isActive={isActiveRoute} tooltip={title} className='flex-1'>
                <BlocksIcon />
                <span>{title}</span>
                <ChevronRightIcon className='ml-auto transition-transform duration-200 group-data-[open]/collapsible:rotate-90' />
              </SidebarMenuButton>
            }
          />
          <button
            type='button'
            onClick={handleCreate}
            className='inline-flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground group-data-[collapsible=icon]:hidden'
            title='新会话'
          >
            <PlusIcon className='size-3.5' />
          </button>
        </div>
        <CollapsibleContent>
          <SidebarMenuSub>

            {sessions.length === 0 ? (
              <SidebarMenuSubItem>
                <div className='px-2 py-1 text-[11px] text-muted-foreground/60'>
                  还没有会话
                </div>
              </SidebarMenuSubItem>
            ) : (
              sessions.map((s) => {
                const active = s.id === activeId
                const label = s.title || s.id.slice(0, 12) + '…'
                return (
                  <SidebarMenuSubItem key={s.id}>
                    <div className='group/session flex items-center'>
                      <SidebarMenuSubButton
                        render={<Link to='/sessions' search={{ s: s.id }} />}
                        isActive={active}
                        className='flex-1 min-w-0'
                      >
                        <span className='truncate' title={s.title || s.id}>
                          {label}
                        </span>
                      </SidebarMenuSubButton>
                      <button
                        type='button'
                        onClick={(e) => handleDelete(e, s.id)}
                        className='ml-1 inline-flex size-6 shrink-0 items-center justify-center rounded text-muted-foreground/0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover/session:text-muted-foreground/60'
                        title='删除会话'
                      >
                        <Trash2Icon className='size-3' />
                      </button>
                    </div>
                  </SidebarMenuSubItem>
                )
              })
            )}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  )
}
