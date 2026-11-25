import { useState } from 'react'
import { useApi, type Subscription } from '../lib/api'
import { Modal, PageHeader } from '../components/ui'
import { date, shortId } from '../lib/format'
import { DataState, FilterTabs, RowActions, StatusPill, ToastHost, useAdminActions } from './shared'

type SubscriptionFilter = 'all' | 'active' | 'expired' | 'canceled'

const FILTERS: { value: SubscriptionFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'active', label: 'Активные' },
  { value: 'expired', label: 'Истёкшие' },
  { value: 'canceled', label: 'Отменённые' },
]

export default function SubscriptionsSection({ canManage }: { canManage: boolean }) {
  const [filter, setFilter] = useState<SubscriptionFilter>('all')
  const [canceling, setCanceling] = useState<Subscription | null>(null)
  const { toast, notify, hideToast, busy, run } = useAdminActions()
  const path = `/api/v1/admin/subscriptions${filter === 'all' ? '' : `?status=${filter}`}`
  const { data, error, loading, reload } = useApi<Subscription[]>(path)

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
      <PageHeader title="Подписки" subtitle="Активные периоды и лимиты генераций." />
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
                    <th>Генерации</th>
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
                        {subscription.generations_used} / {subscription.generations_limit}
                      </td>
                      <td>
                        {canManage && subscription.status === 'active' ? (
                          <RowActions>
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
