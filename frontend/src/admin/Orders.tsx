import { useState } from 'react'
import { useApi, type Order } from '../lib/api'
import { Modal, PageHeader } from '../components/ui'
import { date, money, shortId } from '../lib/format'
import { DataState, FilterTabs, RowActions, StatusPill, ToastHost, useAdminActions } from './shared'

type OrderFilter = 'all' | 'paid' | 'fulfilled' | 'pending' | 'refunded' | 'canceled'

const ORDER_FILTERS: { value: OrderFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'paid', label: 'Оплаченные' },
  { value: 'fulfilled', label: 'Выполненные' },
  { value: 'pending', label: 'Ожидают' },
  { value: 'refunded', label: 'Возвраты' },
  { value: 'canceled', label: 'Отменённые' },
]

export default function OrdersSection({ canManage }: { canManage: boolean }) {
  const [filter, setFilter] = useState<OrderFilter>('all')
  const [details, setDetails] = useState<Order | null>(null)
  const [refunding, setRefunding] = useState<Order | null>(null)
  const { toast, notify, hideToast, busy, run } = useAdminActions()
  const path = `/api/v1/admin/orders${filter === 'all' ? '' : `?status=${filter}`}`
  const { data, error, loading, reload } = useApi<Order[]>(path)

  async function handleRefund() {
    if (!refunding) return
    const result = await run<{ ok: boolean }>(`/api/v1/admin/orders/${refunding.id}/refund`, { method: 'POST' })
    if (result) {
      notify('Возврат оформлен')
      setRefunding(null)
      setDetails(null)
      reload()
    }
  }

  async function handleRetry(order: Order) {
    const result = await run<Order>(`/api/v1/admin/orders/${order.id}/retry-delivery`, { method: 'POST' })
    if (result) {
      notify('Повторная доставка запущена')
      setDetails(result)
      reload()
    }
  }

  return (
    <>
      <PageHeader title="Заказы" subtitle="Оплаты, доставка и возвраты." />
      <FilterTabs value={filter} options={ORDER_FILTERS} onChange={setFilter} />

      <section className="card p-5">
        <DataState loading={loading} error={error} onRetry={reload} empty={!data?.length}>
          {data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Заказ</th>
                    <th>Создан</th>
                    <th>Позиции</th>
                    <th>Сумма</th>
                    <th>Статус</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((order) => (
                    <tr key={order.id}>
                      <td className="font-mono text-xs">{shortId(order.id)}</td>
                      <td className="whitespace-nowrap text-xs text-ink-500">{date(order.created_at, true)}</td>
                      <td>
                        <p className="max-w-[240px] truncate">{order.items.map((item) => item.title).join(', ') || '—'}</p>
                        <p className="hint">{order.items.length} шт.</p>
                      </td>
                      <td className="whitespace-nowrap font-medium">
                        {money(order.total_minor, order.currency)}
                        {order.total_stars > 0 && <span className="hint block">{order.total_stars} ★</span>}
                      </td>
                      <td><StatusPill value={order.status} /></td>
                      <td>
                        <RowActions>
                          <button type="button" className="btn-ghost btn-sm" onClick={() => setDetails(order)}>
                            Детали
                          </button>
                          {order.status !== 'fulfilled' && order.status !== 'refunded' && (
                            <button type="button" className="btn-ghost btn-sm" onClick={() => void handleRetry(order)}>
                              Повторить доставку
                            </button>
                          )}
                          {canManage && ['paid', 'fulfilled'].includes(order.status) && (
                            <button type="button" className="btn-danger btn-sm" onClick={() => setRefunding(order)}>
                              Возврат
                            </button>
                          )}
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

      <Modal open={Boolean(details)} title="Детали заказа" onClose={() => setDetails(null)}>
        {details && (
          <div className="space-y-5">
            <div className="card-muted px-4 py-3 text-sm">
              <p>Заказ <span className="font-mono">{shortId(details.id)}</span> от {date(details.created_at, true)}</p>
              <p className="mt-1">Сумма: {money(details.total_minor, details.currency)} · {details.total_stars} ★</p>
              <p className="hint">Оплачен: {date(details.paid_at, true)} · Выполнен: {date(details.fulfilled_at, true)}</p>
            </div>
            <div>
              <h3 className="label">Позиции</h3>
              <div className="space-y-2">
                {details.items.map((item) => (
                  <div key={item.id} className="flex items-start justify-between gap-3 text-sm">
                    <span>
                      {item.title} <span className="hint">× {item.quantity}</span>
                    </span>
                    <span className="whitespace-nowrap">{money(item.total_minor, details.currency)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h3 className="label">Платежи</h3>
              {details.payments.length === 0 ? (
                <p className="hint">Платежей нет.</p>
              ) : (
                <div className="space-y-2">
                  {details.payments.map((payment) => (
                    <div key={payment.id} className="flex items-center justify-between gap-3 text-sm">
                      <span>{payment.provider} · {shortId(payment.provider_payment_id)}</span>
                      <span className="flex items-center gap-2">
                        {money(payment.amount_minor, payment.currency)}
                        <StatusPill value={payment.status} />
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      <Modal open={Boolean(refunding)} title="Оформить возврат?" onClose={() => setRefunding(null)}>
        <p className="text-sm text-ink-600">
          По заказу <span className="font-mono">{shortId(refunding?.id)}</span> будет возвращена сумма{' '}
          {money(refunding?.total_minor ?? 0, refunding?.currency)}. Доступ пользователя будет отозван.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={() => setRefunding(null)}>Отмена</button>
          <button type="button" className="btn-danger" disabled={busy} onClick={() => void handleRefund()}>
            Вы уверены? Вернуть
          </button>
        </div>
      </Modal>

      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}
