import type { Dashboard } from '../lib/api'
import { useApi } from '../lib/api'
import { Badge, PageHeader, StatCard } from '../components/ui'
import { compactMoney, date, money, plural, shortId } from '../lib/format'
import { DataState, ToastHost, useAdminActions } from './shared'

function RevenueChart({ points }: { points: Dashboard['daily'] }) {
  if (points.length === 0) {
    return <p className="hint">Пока нет данных по выручке.</p>
  }
  const max = Math.max(1, ...points.map((point) => Math.max(0, point.revenue_minor)))

  return (
    <div>
      <div className="flex h-44 items-end gap-[3px] overflow-x-auto sm:gap-1.5">
        {points.map((point) => (
          <div
            key={point.day}
            title={`${date(point.day)} · ${money(point.revenue_minor)} · ${point.users} ${plural(point.users, ['пользователь', 'пользователя', 'пользователей'])}`}
            className="flex h-full min-w-[10px] flex-1 flex-col justify-end"
          >
            <div
              className="w-full rounded-t bg-gold-400/80 transition hover:bg-gold-500"
              style={{ height: `${Math.max(2, (Math.max(0, point.revenue_minor) / max) * 100)}%` }}
            />
          </div>
        ))}
      </div>
      <div className="mt-3 flex justify-between text-xs text-ink-400">
        <span>{date(points[0].day)}</span>
        <span>{date(points[points.length - 1].day)}</span>
      </div>
    </div>
  )
}

export default function DashboardSection() {
  const { data, error, loading, reload } = useApi<Dashboard>('/api/v1/admin/dashboard')
  const { toast, hideToast } = useAdminActions()

  return (
    <>
      <PageHeader title="Обзор" subtitle="Ключевые показатели бизнеса за последние 30 дней." />

      <DataState loading={loading} error={error} onRetry={reload} empty={!data}>
        {data && (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Выручка за 30 дней" value={compactMoney(data.revenue_30d_minor)} accent />
              <StatCard label="MRR" value={compactMoney(data.mrr_minor)} hint={`ARPU ${money(data.arpu_minor)}`} />
              <StatCard
                label="Прибыль за 30 дней"
                value={
                  <span className={data.profit_30d_minor < 0 ? 'text-red-600' : undefined}>
                    {compactMoney(data.profit_30d_minor)}
                  </span>
                }
                hint={`Возвраты ${compactMoney(data.refunds_30d_minor)} · расходы ${compactMoney(data.expenses_30d_minor)} · AI ${compactMoney(data.ai_cost_30d_minor)}`}
              />
              <StatCard label="Покупатели" value={data.buyers} hint={`Всего пользователей: ${data.total_users}`} />
              <StatCard label="Активные подписки" value={data.active_subscriptions} />
              <StatCard label="Новые пользователи" value={data.new_users_30d} hint="За 30 дней" />
              <StatCard label="Открытые тикеты" value={data.open_tickets} />
              <StatCard label="Ожидающие выплаты" value={data.pending_payouts} />
            </div>

            <section className="card p-5">
              <div className="mb-5 flex items-baseline justify-between gap-3">
                <h2 className="font-display text-lg font-semibold">Динамика выручки</h2>
                <span className="hint">Ежедневно</span>
              </div>
              <RevenueChart points={data.daily} />
            </section>

            <div className="grid gap-6 lg:grid-cols-2">
              <section className="card p-5">
                <h2 className="mb-4 font-display text-lg font-semibold">Топ товаров</h2>
                {data.top_products.length === 0 ? (
                  <p className="hint">Продаж пока нет.</p>
                ) : (
                  <div className="space-y-4">
                    {data.top_products.map((product, index) => (
                      <div key={`${product.title}-${index}`}>
                        <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
                          <span className="truncate text-ink-800">{product.title}</span>
                          <span className="whitespace-nowrap font-medium">
                            {compactMoney(product.revenue_minor)}
                          </span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-ink-100">
                          <div
                            className="h-full rounded-full bg-gold-400"
                            style={{
                              width: `${Math.max(
                                4,
                                (product.revenue_minor /
                                  Math.max(1, data.top_products[0].revenue_minor)) *
                                  100,
                              )}%`,
                            }}
                          />
                        </div>
                        <p className="hint mt-1">
                          {product.orders_count} {plural(product.orders_count, ['заказ', 'заказа', 'заказов'])}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="card p-5">
                <h2 className="mb-4 font-display text-lg font-semibold">Последние заказы</h2>
                {data.recent_orders.length === 0 ? (
                  <p className="hint">Заказов пока нет.</p>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Заказ</th>
                          <th>Дата</th>
                          <th>Сумма</th>
                          <th>Статус</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.recent_orders.map((order) => (
                          <tr key={order.id}>
                            <td className="font-mono text-xs">{shortId(order.id)}</td>
                            <td className="whitespace-nowrap">{date(order.created_at, true)}</td>
                            <td className="whitespace-nowrap font-medium">{money(order.total_minor, order.currency)}</td>
                            <td><Badge value={order.status === 'fulfilled' ? 'succeeded' : order.status} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </div>
          </div>
        )}
      </DataState>

      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}
