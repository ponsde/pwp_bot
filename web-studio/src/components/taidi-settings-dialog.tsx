// taidi-overlay: runtime settings drawer for live-editing LLM + OV_VLM
// credentials. Slides in from the right so the panel is short vertically
// and wide horizontally, with LLM / OV_VLM laid out side-by-side.
//
// OV_EMBEDDING_* is shown read-only: swapping the embedding model
// invalidates the existing vector index, so we refuse to edit it here.
import * as React from 'react'
import { toast } from 'sonner'

import { Button } from '#/components/ui/button'
import { Input } from '#/components/ui/input'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '#/components/ui/sheet'

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
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side='right'
        className='flex w-full max-w-[var(--settings-sheet-width)] flex-col gap-4 sm:max-w-[var(--settings-sheet-width)]'
        style={{ '--settings-sheet-width': 'min(780px, 90vw)' } as React.CSSProperties}
      >
        <SheetHeader>
          <SheetTitle>运行时设置</SheetTitle>
          <SheetDescription>
            在线修改 LLM / OV VLM 凭据，保存后下一次请求自动生效。Embedding 不可改
            （改了会使已有的向量索引失效）。留空 API Key 表示"保持现有值不变"。
          </SheetDescription>
        </SheetHeader>

        <div className='flex-1 overflow-y-auto px-4'>
          {loadError ? (
            <div className='rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive'>
              加载失败：{loadError}
            </div>
          ) : !snapshot ? (
            <div className='text-sm text-muted-foreground'>加载中…</div>
          ) : (
            <div className='space-y-6'>
              <div className='grid gap-4 md:grid-cols-2'>
                <section className='rounded-lg border bg-card/50 p-4'>
                  <div className='mb-3 text-sm font-medium'>助手 LLM</div>
                  <div className='space-y-3'>
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
                  </div>
                </section>

                <section className='rounded-lg border bg-card/50 p-4'>
                  <div className='mb-3 text-sm font-medium'>OpenViking VLM</div>
                  <div className='space-y-3'>
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
                  </div>
                </section>
              </div>

              <section className='rounded-lg border border-dashed bg-muted/30 px-4 py-3 text-xs text-muted-foreground'>
                <div className='mb-1 font-medium text-foreground/80'>
                  OpenViking Embedding（只读，改动会使向量索引失效）
                </div>
                <div className='grid gap-x-4 gap-y-1 sm:grid-cols-2'>
                  <span>Model: {snapshot.ov_embedding.model || '未配置'}</span>
                  <span>Dim: {snapshot.ov_embedding.dimension || '—'}</span>
                  <span className='sm:col-span-2'>
                    API Base: {snapshot.ov_embedding.api_base || '—'}
                  </span>
                </div>
              </section>
            </div>
          )}
        </div>

        <SheetFooter className='flex-row justify-end gap-2'>
          <Button variant='outline' onClick={() => onOpenChange(false)} disabled={saving}>
            取消
          </Button>
          <Button onClick={() => void onSave()} disabled={!snapshot || saving}>
            {saving ? '保存中…' : '保存'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
