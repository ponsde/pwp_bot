// taidi-overlay: runtime settings dialog for live-editing LLM + OV_VLM
// credentials. Replaces the upstream ConnectionDialog (which asked for a
// remote OV server baseUrl — irrelevant for our embedded deploy).
//
// OV_EMBEDDING_* is shown read-only: swapping the embedding model
// invalidates the existing vector index, so we refuse to edit it via
// this path.
import * as React from 'react'

import { Button } from '#/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '#/components/ui/dialog'
import { Field, FieldContent, FieldGroup, FieldLabel, FieldSet } from '#/components/ui/field'
import { Input } from '#/components/ui/input'
import { toast } from 'sonner'

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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-xl'>
        <DialogHeader>
          <DialogTitle>运行时设置</DialogTitle>
          <DialogDescription>
            在线修改 LLM / OV VLM 凭据。embedding 不可改（会使已有向量索引失效）。
            空的 API Key 字段表示"保持现有不变"。
          </DialogDescription>
        </DialogHeader>

        {loadError ? (
          <div className='rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive'>
            加载失败：{loadError}
          </div>
        ) : !snapshot ? (
          <div className='text-sm text-muted-foreground'>加载中…</div>
        ) : (
          <FieldSet className='space-y-4'>
            <FieldGroup>
              <div className='text-sm font-medium'>助手 LLM</div>
              <Field>
                <FieldLabel>API Base</FieldLabel>
                <FieldContent>
                  <Input value={llmBase} onChange={(e) => setLlmBase(e.target.value)} />
                </FieldContent>
              </Field>
              <Field>
                <FieldLabel>Model</FieldLabel>
                <FieldContent>
                  <Input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} />
                </FieldContent>
              </Field>
              <Field>
                <FieldLabel>API Key</FieldLabel>
                <FieldContent>
                  <Input
                    type='password'
                    placeholder={snapshot.llm.api_key_masked || '未配置'}
                    value={llmKey}
                    onChange={(e) => setLlmKey(e.target.value)}
                  />
                </FieldContent>
              </Field>
            </FieldGroup>

            <FieldGroup>
              <div className='text-sm font-medium'>OpenViking VLM</div>
              <Field>
                <FieldLabel>API Base</FieldLabel>
                <FieldContent>
                  <Input value={vlmBase} onChange={(e) => setVlmBase(e.target.value)} />
                </FieldContent>
              </Field>
              <Field>
                <FieldLabel>Model</FieldLabel>
                <FieldContent>
                  <Input value={vlmModel} onChange={(e) => setVlmModel(e.target.value)} />
                </FieldContent>
              </Field>
              <Field>
                <FieldLabel>API Key</FieldLabel>
                <FieldContent>
                  <Input
                    type='password'
                    placeholder={snapshot.ov_vlm.api_key_masked || '未配置'}
                    value={vlmKey}
                    onChange={(e) => setVlmKey(e.target.value)}
                  />
                </FieldContent>
              </Field>
            </FieldGroup>

            <FieldGroup>
              <div className='text-sm font-medium text-muted-foreground'>
                OpenViking Embedding（只读）
              </div>
              <div className='text-xs text-muted-foreground'>
                Model: {snapshot.ov_embedding.model || '未配置'} · Dim:{' '}
                {snapshot.ov_embedding.dimension || '—'}
                <br />
                API Base: {snapshot.ov_embedding.api_base || '—'}
              </div>
            </FieldGroup>
          </FieldSet>
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
