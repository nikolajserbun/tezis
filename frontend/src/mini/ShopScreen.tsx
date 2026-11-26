import { useState } from 'react'
import { EmptyState, ErrorState, PageHeader, Spinner } from '../components/ui'
import { money, plural } from '../lib/format'
import type { Invoice, Order, Product } from '../lib/api'
import { useMini, useMiniApi } from './context'
import { BlockTitle, OrdersList, StarsPrice } from './parts'
import { openInvoice } from './telegram'

type CatalogKind = 'all' | 'subscription' | 'digital'

const FILTERS: { value: CatalogKind; label: string }[] = [
  { value: 'all', label: 'Всё' },
  { value: 'subscription', label: 'Подписки' },
  { value: 'digital', label: 'Продукты' },
]

export function ShopScreen() {
  const { config, run, bumpOrders, refreshMe, notify, haptic } = useMini()
  const [kind, setKind] = useState<CatalogKind>('all')
  const [busyId, setBusyId] = useState<string | null>(null)
  const path = kind === 'all' ? '/api/v1/catalog' : `/api/v1/catalog?kind=${kind}`
  const catalog = useMiniApi<Product[]>(path)
  const isDev = config.app_env !== 'prod'

  const buyStars = async (product: Product): Promise<void> => {
    setBusyId(product.id)
    const order = await run<Order>('/api/v1/orders', {
      method: 'POST',
      body: { product_id: product.id },
    })
    if (!order) {
      setBusyId(null)
      return
    }
    const invoice = await run<Invoice>(`/api/v1/orders/${order.id}/pay/stars`, { method: 'POST' })
    setBusyId(null)
    if (!invoice) return
    const opened = openInvoice(invoice.invoice_url, (status) => {
      bumpOrders()
      refreshMe()
      if (status === 'paid') notify('Оплата прошла. Обновляем статус…')
      else if (status === 'cancelled') notify('Оплата отменена')
      else if (status === 'failed') notify('Оплата не прошла. Попробуйте ещё раз.')
    })
    notify(opened ? 'Счёт на оплату открыт' : `Ссылка на оплату: ${invoice.invoice_url}`)
    bumpOrders()
  }

  const buyDev = async (product: Product): Promise<void> => {
    setBusyId(product.id)
    const order = await run<Order>('/api/v1/orders', {
      method: 'POST',
      body: { product_id: product.id },
    })
    if (!order) {
      setBusyId(null)
      return
    }
    const paid = await run<Order>(`/api/v1/orders/${order.id}/pay/dev`, { method: 'POST' })
    setBusyId(null)
    if (!paid) return
    notify('Тестовая покупка оформлена')
    bumpOrders()
    refreshMe()
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Магазин" subtitle="Подписки и инструменты для вашего контента." />

      <section>
        <BlockTitle>Заказы на оплате</BlockTitle>
        <OrdersList pendingOnly />
      </section>

      <section>
        <div className="no-scrollbar -mx-4 mb-4 flex gap-2 overflow-x-auto px-4">
          {FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              className={filter.value === kind ? 'btn-primary btn-sm' : 'btn-ghost btn-sm'}
              onClick={() => {
                haptic()
                setKind(filter.value)
              }}
            >
              {filter.label}
            </button>
          ))}
        </div>

        {catalog.loading ? (
          <Spinner label="Загружаем каталог…" />
        ) : catalog.error ? (
          <ErrorState message={catalog.error} onRetry={catalog.reload} />
        ) : !catalog.data?.length ? (
          <EmptyState title="Каталог пуст" text="Заглядите сюда позже." />
        ) : (
          <div className="space-y-4">
            {catalog.data.map((product, index) => {
              const busy = busyId === product.id
              return (
                <article
                  key={product.id}
                  className="card mini-reveal overflow-hidden"
                  style={{ animationDelay: `${Math.min(index, 6) * 60}ms` }}
                >
                  {product.cover_url && (
                    <img
                      src={product.cover_url}
                      alt=""
                      className="h-36 w-full object-cover"
                      loading="lazy"
                    />
                  )}
                  <div className="p-5">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="font-display text-xl font-semibold leading-snug text-ink-900">
                        {product.title}
                      </h3>
                      <span className="badge-gold whitespace-nowrap">
                        {product.kind === 'subscription' ? 'Подписка' : 'Продукт'}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-ink-600">{product.description}</p>

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <span className="font-display text-2xl font-semibold text-ink-900">
                        {money(product.price_minor, product.currency)}
                      </span>
                      {product.price_stars !== null && <StarsPrice value={product.price_stars} />}
                    </div>

                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-500">
                      {product.duration_days !== null && (
                        <span>
                          {product.duration_days} {plural(product.duration_days, ['день', 'дня', 'дней'])}
                        </span>
                      )}
                      {product.generations_per_month !== null && (
                        <span>
                          {product.generations_per_month}{' '}
                          {plural(product.generations_per_month, [
                            'генерация',
                            'генерации',
                            'генераций',
                          ])}{' '}
                          в месяц
                        </span>
                      )}
                      <span>{product.brand_limit} бренд-профиля</span>
                    </div>

                    {product.features.length > 0 && (
                      <ul className="mt-4 space-y-1.5 border-t border-ink-100 pt-4">
                        {product.features.map((feature) => (
                          <li key={feature} className="flex gap-2 text-sm text-ink-700">
                            <span className="text-gold-600" aria-hidden>
                              ✦
                            </span>
                            <span>{feature}</span>
                          </li>
                        ))}
                      </ul>
                    )}

                    <div className="mt-5 flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="btn-gold flex-1"
                        disabled={busy}
                        onClick={() => void buyStars(product)}
                      >
                        {busy ? 'Создаём счёт…' : 'Купить в Stars'}
                      </button>
                      {isDev && (
                        <button
                          type="button"
                          className="btn-primary flex-1"
                          disabled={busy}
                          onClick={() => void buyDev(product)}
                        >
                          Тестовая оплата
                        </button>
                      )}
                    </div>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
