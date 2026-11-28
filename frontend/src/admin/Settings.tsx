import { useEffect, useState } from 'react'
import { useApi, type Setting } from '../lib/api'
import { Field, PageHeader } from '../components/ui'
import { date } from '../lib/format'
import { DataState, ToastHost, useAdminActions } from './shared'

type ValueKind = 'boolean' | 'number' | 'json' | 'string'

const KEY_LABELS: Record<string, string> = {
  support_username: 'Поддержка в Telegram',
  referral_bonus_minor: 'Бонус за первого друга, коп.',
  free_neurons: 'Бесплатные Neurons (без подписки, не обновляются)',
  maintenance_mode: 'Режим обслуживания',
  community_chat_id: 'ID чата сообщества',
  stars_rub_rate: 'Курс звёзд, ₽',
}

function kindOf(value: unknown): ValueKind {
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'number') return 'number'
  if (value !== null && typeof value === 'object') return 'json'
  if (value === null) return 'json'
  return 'string'
}

function draftOf(value: unknown): string {
  if (typeof value === 'string') return value
  if (value === undefined) return ''
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return JSON.stringify(value, null, 2)
}

function parseDraft(key: string, raw: string, kind: ValueKind): unknown {
  if (kind === 'boolean') {
    if (raw !== 'true' && raw !== 'false') throw new Error(`«${key}»: выберите да или нет`)
    return raw === 'true'
  }
  if (kind === 'number') {
    const value = Number(raw)
    if (!Number.isFinite(value)) throw new Error(`«${key}»: введите число`)
    return value
  }
  if (kind === 'json') {
    try {
      return JSON.parse(raw) as unknown
    } catch {
      throw new Error(`«${key}»: некорректный JSON`)
    }
  }
  return raw
}

export default function SettingsSection({ isOwner }: { isOwner: boolean }) {
  const { data, error, loading, reload, setData } = useApi<Setting[]>('/api/v1/admin/settings')
  const { toast, notify, hideToast, busy, run } = useAdminActions()
  const [drafts, setDrafts] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!data) return
    const next: Record<string, string> = {}
    for (const setting of data) next[setting.key] = draftOf(setting.value)
    setDrafts(next)
  }, [data])

  async function handleSave() {
    if (!data) return
    try {
      const values: Record<string, unknown> = {}
      for (const setting of data) {
        values[setting.key] = parseDraft(setting.key, drafts[setting.key] ?? '', kindOf(setting.value))
      }
      const result = await run<Setting[]>('/api/v1/admin/settings', {
        method: 'PATCH',
        body: { values },
      })
      if (result) {
        setData(result)
        notify('Настройки сохранены')
        reload()
      }
    } catch (validationError) {
      notify(validationError instanceof Error ? validationError.message : 'Проверьте значения настроек')
    }
  }

  return (
    <>
      <PageHeader
        title="Настройки"
        subtitle="Параметры бота, рефералки и сообщества."
        action={
          isOwner ? (
            <button type="button" className="btn-primary" disabled={busy || !data} onClick={() => void handleSave()}>
              {busy ? 'Сохраняем…' : 'Сохранить изменения'}
            </button>
          ) : undefined
        }
      />

      {!isOwner && (
        <p className="card-muted mb-5 p-4 text-sm text-ink-600">
          Просмотр настроек доступен администраторам. Изменять значения может только владелец.
        </p>
      )}

      <section className="card p-5">
        <DataState loading={loading} error={error} onRetry={reload} empty={!data?.length}>
          {data && (
            <div className="space-y-6">
              {data.map((setting) => {
                const kind = kindOf(setting.value)
                const value = drafts[setting.key] ?? ''
                return (
                  <div key={setting.key} className="grid gap-4 sm:grid-cols-[minmax(180px,1fr)_minmax(240px,2fr)]">
                    <div>
                      <p className="text-sm font-medium text-ink-800">
                        {KEY_LABELS[setting.key] ?? setting.key}
                      </p>
                      <p className="hint font-mono">{setting.key}</p>
                      <p className="hint">Тип: {kind === 'json' ? 'JSON' : kind}</p>
                      <p className="hint">Обновлено: {date(setting.updated_at, true)}</p>
                    </div>
                    <Field label="Значение">
                      {kind === 'boolean' ? (
                        <select
                          className="select"
                          value={value}
                          disabled={!isOwner}
                          onChange={(event) => setDrafts({ ...drafts, [setting.key]: event.target.value })}
                        >
                          <option value="true">Да</option>
                          <option value="false">Нет</option>
                        </select>
                      ) : kind === 'number' ? (
                        <input
                          className="input"
                          type="number"
                          value={value}
                          disabled={!isOwner}
                          onChange={(event) => setDrafts({ ...drafts, [setting.key]: event.target.value })}
                        />
                      ) : kind === 'json' ? (
                        <textarea
                          className="textarea min-h-[100px] font-mono text-xs"
                          value={value}
                          disabled={!isOwner}
                          onChange={(event) => setDrafts({ ...drafts, [setting.key]: event.target.value })}
                        />
                      ) : (
                        <input
                          className="input"
                          value={value}
                          disabled={!isOwner}
                          onChange={(event) => setDrafts({ ...drafts, [setting.key]: event.target.value })}
                        />
                      )}
                    </Field>
                  </div>
                )
              })}
            </div>
          )}
        </DataState>
      </section>

      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}
