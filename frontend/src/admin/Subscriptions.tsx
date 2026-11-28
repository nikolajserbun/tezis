import { useState, type FormEvent } from 'react'
import { useApi, type Subscription } from '../lib/api'
import { Field, Modal, PageHeader } from '../components/ui'
import { date, shortId } from '../lib/format'
import { DataState, FilterTabs, RowActions, StatusPill, ToastHost, useAdminActions } from './shared'

type SubscriptionFilter = 'all' | 'active' | 'expired' | 'canceled'

const FILTERS: { value: SubscriptionFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'active', label: 'Активные' },
  { value: 'expired', label: 'Истёкшие' },
  { value: 'canceled', label: 'Отменённые' },
]

function toLocalInput(value: string): string {
  const d = new Date(value)
  const offset = d.getTimezoneOffset() * 60_000
  return new Date(d.getTime() - offset).toISOString().slice(0, 16)
}

export default function SubscriptionsSection({ canManage }: { canManage: boolean }) {
  const [filter, setFilter] = useState<SubscriptionFilter>('all')
  const [canceling, setCanceling] = useState<Subscription | null>(null)
  const [editing, setEditing] = useState<Subscription | null>(null)
  const [neuronsPerWeek, setNeuronsPerWeek] = useState('')
  const [expiresAt, setExpiresAt] = useState('')
  const { toast, notify, hideToast, busy, run } = useAdminActions()
  const path = `/api/v1/admin/subscriptions${filter === 'all' ? '' : `?status=${filter}`}`
  const { data, error, loading, reload } = useApi<Subscription[]>(path)

  function openEdit(subscription: Subscription) {
    setEditing(subscription)
    setNeuronsPerWeek(String(subscription.neurons_per_week))
    setExpiresAt(toLocalInput(subscription.expires_at))
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editing) return
    const weekly = Number(neuronsPerWeek)
    if (!Number.isFinite(weekly) || weekly <= 0) {
      notify('Укажите положительное число Neurons в неделю')
      return
    }
    const result = await run<Subscription>(`/api/v1/admin/subscriptions/${editing.id}`, {
      method: 'PATCH',
      body: { neurons_per_week: weekly, expires_at: new Date(expiresAt).toISOString() },
    })
    if (result) {
      notify('Подписка обновлена')
      setEditing(null)
      reload()
    }
  }

  async function handleCancel() {
    if (!canceling) return
    const result = await run<Subscription>(`/api/v1/admin/subscriptions/${canceling.id}/cancel`, {
      method: 'POST',
    })
    if (result) {
      notify('Подписка отменена')
      setCanceling(null)
      reload()
    }
  }

  return (
    <>
      <PageHeader
        title="Подписки"
        subtitle="Активные периоды и еженедельные лимиты Neurons. Тарифы настраиваются в разделе «Товары»."
      />
      <FilterTabs value={filter} options={FILTERS} onChange={setFilter} />

      <section className="card p-5">
        <DataState loading={loading} error={error} onRetry={reload} empty={!data?.length}>
          {data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Пользователь</th>
                    <th>Тариф</th>
                    <th>Статус</th>
                    <th>Период</th>
                    <th>Neurons / нед.</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((subscription) => (
                    <tr key={subscription.id}>
                      <td className="font-mono text-xs">{shortId(subscription.user_id)}</td>
                      <td className="font-medium">{subscription.product_title ?? 'Без названия'}</td>
                      <td><StatusPill value={subscription.status} /></td>
                      <td className="whitespace-nowrap text-xs text-ink-500">
                        {date(subscription.current_period_start)} — {date(subscription.expires_at)}
                        <span className="block">{subscription.auto_renew ? 'Автопродление' : 'Без продления'}</span>
                      </td>
                      <td className="whitespace-nowrap">
                        {subscription.neurons_used} / {subscription.neurons_limit}
                        <span className="block hint">до {date(subscription.current_period_end)}</span>
                      </td>
                      <td>
                        {canManage && subscription.status === 'active' ? (
                          <RowActions>
                            <button type="button" className="btn-ghost btn-sm" onClick={() => openEdit(subscription)}>
                              Изменить
                            </button>
                            <button type="button" className="btn-danger btn-sm" onClick={() => setCanceling(subscription)}>
                              Отменить
                            </button>
                          </RowActions>
                        ) : (
                          <span className="hint">
                            {subscription.status !== 'active' ? 'Завершена' : 'Недостаточно прав'}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </section>

      <Modal open={Boolean(editing)} title="Настроить подписку" onClose={() => setEditing(null)}>
        <form onSubmit={handleSave} className="space-y-4">
          <p className="text-sm text-ink-600">
            Подписка «{editing?.product_title ?? 'Без названия'}» · {shortId(editing?.user_id ?? '')}
          </p>
          <Field label="Neurons в неделю" hint="Пополняется каждые 7 дней, пока подписка активна.">
            <input
              className="input"
              type="number"
              min={1}
              step="1"
              value={neuronsPerWeek}
              onChange={(event) => setNeuronsPerWeek(event.target.value)}
              required
            />
          </Field>
          <Field label="Действует до">
            <input
              className="input"
              type="datetime-local"
              value={expiresAt}
              onChange={(event) => setExpiresAt(event.target.value)}
              required
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>Отмена</button>
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? 'Сохраняем…' : 'Сохранить'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal open={Boolean(canceling)} title="Отменить подписку?" onClose={() => setCanceling(null)}>
        <p className="text-sm text-ink-600">
          Подписка «{canceling?.product_title ?? 'Без названия'}» будет отменена, доступ к сообществу — отозван.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={() => setCanceling(null)}>Отмена</button>
          <button type="button" className="btn-danger" disabled={busy} onClick={() => void handleCancel()}>
            Вы уверены? Отменить
          </button>
        </div>
      </Modal>

      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}
