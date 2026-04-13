// taidi-overlay: runtime settings dialog. Centered, wide-but-short, with
// LLM / OV_VLM sections collapsed by default — click a section header to
// expand its form. OV_EMBEDDING_* is always-visible read-only because
// changing the embedding model would invalidate the existing vector index.
import * as React from 'react'
import { ChevronDownIcon } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '#/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '#/components/ui/dialog'
import { Input } from '#/components/ui/input'
import { cn } from '#/lib/utils'

const ENV_BASE_URL =
  typeof import.meta.env.VITE_API_BASE_URL === 'string'
    ? import.meta.env.VITE_API_BASE_URL.trim().replace(/\/+$/, '')
    : ''

function apiUrl(path: string) {
  return `${ENV_BASE_URL}${path}`
}

type SettingsSnapshot = {
  llm: { api_base: string; api_key_masked: string; model: string }
  ov_vlm: { api_base: string; api_key_masked: string; model: string }
  ov_embedding: { api_base: string; api_key_masked: string; model: string; dimension: number }
}

type UpdatablePayload = {
  llm?: { api_base?: string; api_key?: string; model?: string }
  ov_vlm?: { api_base?: string; api_key?: string; model?: string }
}

type SectionKey = 'llm' | 'vlm'

function Labeled({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <label className='flex flex-col gap-1 text-sm'>
      <span className='text-xs font-medium text-muted-foreground'>{label}</span>
      {children}
    </label>
  )
}

function summary(
  snapshot: SettingsSnapshot[keyof SettingsSnapshot] | undefined,
): string {
  if (!snapshot) return '未配置'
  const parts: string[] = []
  if (snapshot.model) parts.push(snapshot.model)
  if (snapshot.api_base) {
    try {
      parts.push(new URL(snapshot.api_base).host)
    } catch {
      parts.push(snapshot.api_base)
    }
  }
  return parts.join(' · ') || '未配置'
}

export function TaidiSettingsDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [snapshot, setSnapshot] = React.useState<SettingsSnapshot | null>(null)
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)
  const [expanded, setExpanded] = React.useState<SectionKey | null>(null)

  const [llmBase, setLlmBase] = React.useState('')
  const [llmKey, setLlmKey] = React.useState('')
  const [llmModel, setLlmModel] = React.useState('')
  const [vlmBase, setVlmBase] = React.useState('')
  const [vlmKey, setVlmKey] = React.useState('')
  const [vlmModel, setVlmModel] = React.useState('')

  React.useEffect(() => {
    if (!open) return
    setLoadError(null)
    setSnapshot(null)
    setExpanded(null)
    void (async () => {
      try {
        const res = await fetch(apiUrl('/api/settings'))
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        const data = (await res.json()) as SettingsSnapshot
        setSnapshot(data)
        setLlmBase(data.llm.api_base)
        setLlmModel(data.llm.model)
        setLlmKey('')
        setVlmBase(data.ov_vlm.api_base)
        setVlmModel(data.ov_vlm.model)
        setVlmKey('')
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : String(err))
      }
    })()
  }, [open])

  const toggle = (key: SectionKey) =>
    setExpanded((prev) => (prev === key ? null : key))

  const onSave = async () => {
    setSaving(true)
    try {
      const payload: UpdatablePayload = {
        llm: {
          api_base: llmBase,
          model: llmModel,
          ...(llmKey ? { api_key: llmKey } : {}),
        },
        ov_vlm: {
          api_base: vlmBase,
          model: vlmModel,
          ...(vlmKey ? { api_key: vlmKey } : {}),
        },
      }
      const res = await fetch(apiUrl('/api/settings'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(`${res.status}: ${text || res.statusText}`)
      }
      toast.success('设置已保存，下一次请求生效')
      onOpenChange(false)
    } catch (err) {
      toast.error(`保存失败：${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='w-[min(640px,92vw)] max-w-none gap-3'>
        <DialogHeader>
          <DialogTitle>运行时设置</DialogTitle>
          <DialogDescription>
            点击下方分区展开编辑。API Key 留空表示"保持不变"。
          </DialogDescription>
        </DialogHeader>

        {loadError ? (
          <div className='rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive'>
            加载失败：{loadError}
          </div>
        ) : !snapshot ? (
          <div className='text-sm text-muted-foreground'>加载中…</div>
        ) : (
          <div className='flex flex-col gap-2'>
            <CollapsibleSection
              title='助手 LLM'
              summaryText={summary(snapshot.llm)}
              open={expanded === 'llm'}
              onToggle={() => toggle('llm')}
            >
              <Labeled label='API Base'>
                <Input value={llmBase} onChange={(e) => setLlmBase(e.target.value)} />
              </Labeled>
              <Labeled label='Model'>
                <Input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} />
              </Labeled>
              <Labeled label='API Key'>
                <Input
                  type='password'
                  placeholder={snapshot.llm.api_key_masked || '未配置'}
                  value={llmKey}
                  onChange={(e) => setLlmKey(e.target.value)}
                />
              </Labeled>
            </CollapsibleSection>

            <CollapsibleSection
              title='OpenViking VLM'
              summaryText={summary(snapshot.ov_vlm)}
              open={expanded === 'vlm'}
              onToggle={() => toggle('vlm')}
            >
              <Labeled label='API Base'>
                <Input value={vlmBase} onChange={(e) => setVlmBase(e.target.value)} />
              </Labeled>
              <Labeled label='Model'>
                <Input value={vlmModel} onChange={(e) => setVlmModel(e.target.value)} />
              </Labeled>
              <Labeled label='API Key'>
                <Input
                  type='password'
                  placeholder={snapshot.ov_vlm.api_key_masked || '未配置'}
                  value={vlmKey}
                  onChange={(e) => setVlmKey(e.target.value)}
                />
              </Labeled>
            </CollapsibleSection>

            <section className='rounded-md border border-dashed bg-muted/30 px-3 py-2 text-xs text-muted-foreground'>
              <div className='mb-0.5 font-medium text-foreground/80'>
                OpenViking Embedding（只读）
              </div>
              <div>
                {snapshot.ov_embedding.model || '未配置'}
                {snapshot.ov_embedding.dimension
                  ? ` · dim ${snapshot.ov_embedding.dimension}`
                  : ''}
                {snapshot.ov_embedding.api_base
                  ? ` · ${(() => {
                      try {
                        return new URL(snapshot.ov_embedding.api_base).host
                      } catch {
                        return snapshot.ov_embedding.api_base
                      }
                    })()}`
                  : ''}
              </div>
            </section>
          </div>
        )}

        <DialogFooter>
          <Button variant='outline' onClick={() => onOpenChange(false)} disabled={saving}>
            取消
          </Button>
          <Button onClick={() => void onSave()} disabled={!snapshot || saving}>
            {saving ? '保存中…' : '保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function CollapsibleSection({
  title,
  summaryText,
  open,
  onToggle,
  children,
}: {
  title: string
  summaryText: string
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <section className='overflow-hidden rounded-md border bg-card/50'>
      <button
        type='button'
        onClick={onToggle}
        className='flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition-colors hover:bg-accent/40'
      >
        <span className='flex min-w-0 flex-col gap-0.5'>
          <span className='text-sm font-medium'>{title}</span>
          <span className='truncate text-xs text-muted-foreground'>{summaryText}</span>
        </span>
        <ChevronDownIcon
          className={cn('size-4 shrink-0 transition-transform', open && 'rotate-180')}
        />
      </button>
      {open ? <div className='space-y-3 border-t px-3 pb-3 pt-3'>{children}</div> : null}
    </section>
  )
}
