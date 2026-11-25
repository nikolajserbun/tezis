import { useState, type FormEvent } from 'react'
import { useApi, type Broadcast } from '../lib/api'
import { Field, Modal, PageHeader } from '../components/ui'
import { date } from '../lib/format'
import { DataState, RowActions, StatusPill, ToastHost, useAdminActions } from './shared'

type SegmentType = 'all' | 'payers' | 'trial' | 'inactive' | 'expiring'

interface BroadcastForm {
  title: string
  text: string
  segmentType: SegmentType
  days: string
  scheduledAt: string
}

const SEGMENTS: { value: SegmentType; label: string }[] = [
  { value: 'all', label: 'Все пользователи' },
  { value: 'payers', label: 'Платившие' },
  { value: 'trial', label: 'Пробный период' },
  { value: 'inactive', label: 'Неактивные' },
  { value: 'expiring', label: 'Подписка истекает' },
]

function emptyForm(): BroadcastForm {
  return { title: '', text: '', segmentType: 'all', days: '7', scheduledAt: '' }
}

function segmentLabel(segment: Broadcast['segment']): string {
  const type = typeof segment.type === 'string' ? segment.type : 'all'
  const days = typeof segment.days === 'number' ? segment.days : null
  const base = SEGMENTS.find((item) => item.value === type)?.label ?? type
  return days ? `${base} · ${days} дн.` : base
}

export default function BroadcastsSection() {
  const { data, error, loading, reload } = useApi<Broadcast[]>('/api/v1/admin/broadcasts')
  const { toast, notify, hideToast, busy, run } = useAdminActions()
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<BroadcastForm>(emptyForm)
  const [sending, setSending] = useState<Broadcast | null>(null)

  function closeModal() {
    setModalOpen(false)
    setForm(emptyForm())
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    let scheduledAt: string | null = null
    if (form.scheduledAt) {
      const parsed = new Date(form.scheduledAt)
      if (Number.isNaN(parsed.getTime())) {
        notify('Некорректная дата отправки')
        return
      }
      scheduledAt = parsed.toISOString()
    }
    const segment: { type: SegmentType; days?: number } = { type: form.segmentType }
    if (form.segmentType === 'inactive' || form.segmentType === 'expiring') {
      const days = Number(form.days)
      if (!Number.isInteger(days) || days < 1) {
        notify('Количество дней должно быть целым числом больше нуля')
        return
      }
      segment.days = days
    }

    const result = await run<Broadcast>('/api/v1/admin/broadcasts', {
      method: 'POST',
      body: {
        title: form.title.trim(),
        text: form.text.trim(),
        segment,
        scheduled_at: scheduledAt,
      },
    })
    if (result) {
      notify(scheduledAt ? 'Рассылка запланирована' : 'Рассылка создана')
      closeModal()
      reload()
    }
  }

  async function handleSend() {
    if (!sending) return
    const result = await run<{ ok: boolean; queued: boolean }>(`/api/v1/admin/broadcasts/${sending.id}/send`, {
      method: 'POST',
    })
    if (result) {
      notify('Рассылка поставлена в очередь')
      setSending(null)
      reload()
    }
  }

  return (
    <>
      <PageHeader
        title="Рассылки"
        subtitle="Сегментированные сообщения пользователям."
        action={
          <button type="button" className="btn-primary" onClick={() => setModalOpen(true)}>
            Новая рассылка
          </button>
        }
      />

      <section className="card p-5">
        <DataState loading={loading} error={error} onRetry={reload} empty={!data?.length}>
          {data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Заголовок</th>
                    <th>Сегмент</th>
                    <th>Статус</th>
                    <th>Отправка</th>
                    <th>Результат</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((broadcast) => (
                    <tr key={broadcast.id}>
                      <td>
                        <p className="max-w-[260px] font-medium">{broadcast.title}</p>
                        <p className="hint max-w-[260px] truncate" title={broadcast.text}>{broadcast.text}</p>
                      </td>
                      <td className="whitespace-nowrap">{segmentLabel(broadcast.segment)}</td>
                      <td><StatusPill value={broadcast.status} /></td>
                      <td className="whitespace-nowrap text-xs text-ink-500">{date(broadcast.scheduled_at, true)}</td>
                      <td className="whitespace-nowrap text-xs">
                        <span className="text-moss-500">{broadcast.sent_count} отправлено</span>
                        {broadcast.failed_count > 0 && (
                          <span className="block text-red-600">{broadcast.failed_count} ошибок</span>
                        )}
                      </td>
                      <td>
                        <RowActions>
                          {['draft', 'scheduled', 'failed'].includes(broadcast.status) && (
                            <button type="button" className="btn-gold btn-sm" onClick={() => setSending(broadcast)}>
                              Отправить
                            </button>
                          )}
                          <span className="hint">Создана {date(broadcast.created_at)}</span>
                        </RowActions>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </section>

      <Modal open={modalOpen} title="Новая рассылка" onClose={closeModal}>
        <form onSubmit={handleCreate} className="space-y-4">
          <Field label="Заголовок">
            <input
              className="input"
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              maxLength={160}
              required
            />
          </Field>
          <Field label="Текст">
            <textarea
              className="textarea"
              value={form.text}
              onChange={(event) => setForm({ ...form, text: event.target.value })}
              maxLength={4000}
              required
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Сегмент">
              <select
                className="select"
                value={form.segmentType}
                onChange={(event) => setForm({ ...form, segmentType: event.target.value as SegmentType })}
              >
                {SEGMENTS.map((segment) => (
                  <option key={segment.value} value={segment.value}>{segment.label}</option>
                ))}
              </select>
            </Field>
            {(form.segmentType === 'inactive' || form.segmentType === 'expiring') && (
              <Field label="Период, дней">
                <input
                  className="input"
                  type="number"
                  min={1}
                  value={form.days}
                  onChange={(event) => setForm({ ...form, days: event.target.value })}
                  required
                />
              </Field>
            )}
          </div>
          <Field label="Запланированная отправка" hint="Пусто — отправить вручную. Время указывается в вашем часовом поясе.">
            <input
              className="input"
              type="datetime-local"
              value={form.scheduledAt}
              onChange={(event) => setForm({ ...form, scheduledAt: event.target.value })}
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-ghost" onClick={closeModal}>Отмена</button>
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? 'Создаём…' : 'Создать'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal open={Boolean(sending)} title="Отправить рассылку?" onClose={() => setSending(null)}>
        <p className="text-sm text-ink-600">
          Рассылка «{sending?.title}» будет отправлена сегменту «{sending ? segmentLabel(sending.segment) : ''}».
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={() => setSending(null)}>Отмена</button>
          <button type="button" className="btn-gold" disabled={busy} onClick={() => void handleSend()}>
            Вы уверены? Отправить
          </button>
        </div>
      </Modal>

      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}
