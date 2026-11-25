import { useState } from 'react'
import type { ReactNode } from 'react'
import { Badge, EmptyState, ErrorState, Modal, Spinner } from '../components/ui'
import { copyToClipboard, date, money, shortId } from '../lib/format'
import type { Invoice, Order } from '../lib/api'
import { useMini, useMiniApi } from './context'
import { openExternal } from './telegram'
import type { Tab } from './types'

export function TabIcon({ tab }: { tab: Tab }) {
  const common = {
    width: 21,
    height: 21,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }

  if (tab === 'home') {
    return (
      <svg {...common}>
        <path d="M3 10.5 12 3l9 7.5" />
        <path d="M5.5 9.8V20h13V9.8" />
        <path d="M9.5 20v-6h5v6" />
      </svg>
    )
  }
  if (tab === 'studio') {
    return (
      <svg {...common}>
        <path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z" />
        <path d="M18.5 16.5 19.2 19l2.3.8-2.3.8-.7 2.4" transform="translate(0 -2)" />
        <path d="M5 16.5h4" />
      </svg>
    )
  }
  if (tab === 'chat') {
    return (
      <svg {...common}>
        <path d="M20 12a7.5 7.5 0 0 1-7.5 7.5H7L4 22v-4.2A7.5 7.5 0 1 1 20 12Z" />
        <path d="M8.5 11h7M8.5 14.5h4" />
      </svg>
    )
  }
  if (tab === 'shop') {
    return (
      <svg {...common}>
        <path d="M4 8h16l-1.3 12H5.3L4 8Z" />
        <path d="M9 9V6a3 3 0 0 1 6 0v3" />
      </svg>
    )
  }
  if (tab === 'orders') {
    return (
      <svg {...common}>
        <path d="M6 3h12v18l-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5L6 21V3Z" />
        <path d="M9 8h6M9 12h6M9 16h3" />
      </svg>
    )
  }
  return (
    <svg {...common}>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c.7-3.6 3.4-5.5 7-5.5s6.3 1.9 7 5.5" />
    </svg>
  )
}

export function BootView({
  label,
  error,
  onRetry,
}: {
  label: string
  error?: string | null
  onRetry?: () => void
}) {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-5 py-10">
      <p className="font-display text-3xl font-semibold tracking-tight text-ink-900">Тезис</p>
      <div className="mt-8">
        {error ? (
          <ErrorState message={error} onRetry={onRetry} />
        ) : (
          <Spinner label={label} />
        )}
      </div>
    </main>
  )
}

export function BlockTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="font-display text-lg font-semibold tracking-tight text-ink-900">{children}</h2>
      {action}
    </div>
  )
}

export function StarsPrice({ value }: { value: number }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-gold-100 px-2.5 py-1 text-xs font-medium text-gold-700">
      <span aria-hidden>✦</span> {value} Stars
    </span>
  )
}

export function CopyButton({
  text,
  label = 'Скопировать',
  className = '',
}: {
  text: string
  label?: string
  className?: string
}) {
  const { notify, haptic } = useMini()

  const copy = (): void => {
    haptic()
    void copyToClipboard(text).then((ok) => notify(ok ? 'Скопировано' : 'Не удалось скопировать'))
  }

  return (
    <button type="button" className={`btn-ghost btn-sm ${className}`} onClick={copy}>
      {label}
    </button>
  )
}

export function OrderCard({ order }: { order: Order }) {
  const { run, bumpOrders, refreshMe, notify, isDev, haptic } = useMini()
  const [busy, setBusy] = useState(false)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const pending = order.status === 'pending'

  const payStars = async (): Promise<void> => {
    setBusy(true)
    const invoice = await run<Invoice>(`/api/v1/orders/${order.id}/pay/stars`, { method: 'POST' })
    setBusy(false)
    if (!invoice) return
    const opened = openExternal(invoice.invoice_url)
    notify(opened ? 'Счёт на оплату открыт' : `Ссылка на оплату: ${invoice.invoice_url}`)
    bumpOrders()
  }

  const payDev = async (): Promise<void> => {
    setBusy(true)
    const updated = await run<Order>(`/api/v1/orders/${order.id}/pay/dev`, { method: 'POST' })
    setBusy(false)
    if (!updated) return
    notify('Заказ оплачен в тестовом режиме')
    bumpOrders()
    refreshMe()
  }

  const cancel = async (): Promise<void> => {
    setBusy(true)
    const updated = await run<Order>(`/api/v1/orders/${order.id}/cancel`, { method: 'POST' })
    setBusy(false)
    if (!updated) return
    setConfirmCancel(false)
    notify('Заказ отменён')
    bumpOrders()
  }

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-ink-900">Заказ {shortId(order.id)}</p>
          <p className="hint mt-1">{date(order.created_at, true)}</p>
        </div>
        <Badge value={order.status} />
      </div>

      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="font-display text-xl font-semibold text-ink-900">
          {money(order.total_minor, order.currency)}
        </span>
        <span className="hint">{order.total_stars} Stars</span>
      </div>

      <div className="mt-3 border-t border-ink-100 pt-3">
        <p className="label">Состав заказа</p>
        {order.items.length ? (
          <div className="space-y-1">
            {order.items.map((item) => (
              <div key={item.id} className="flex justify-between gap-3 text-sm text-ink-700">
                <span>
                  {item.title} <span className="text-ink-400">× {item.quantity}</span>
                </span>
                <span className="shrink-0">{money(item.total_minor, order.currency)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-500">Позиций нет</p>
        )}
      </div>

      {order.paid_at && <p className="hint mt-3">Оплачен: {date(order.paid_at, true)}</p>}

      {pending && (
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" className="btn-gold btn-sm" disabled={busy} onClick={() => void payStars()}>
            Оплатить в Stars
          </button>
          {isDev && (
            <button type="button" className="btn-primary btn-sm" disabled={busy} onClick={() => void payDev()}>
              Тестовая оплата
            </button>
          )}
          <button
            type="button"
            className="btn-danger btn-sm"
            disabled={busy}
            onClick={() => {
              haptic()
              setConfirmCancel(true)
            }}
          >
            Отменить
          </button>
        </div>
      )}

      <Modal open={confirmCancel} title="Отменить заказ?" onClose={() => setConfirmCancel(false)}>
        <p className="text-sm leading-relaxed text-ink-600">
          Заказ {shortId(order.id)} будет отменён, списание не произойдёт.
        </p>
        <div className="mt-5 flex gap-2">
          <button
            type="button"
            className="btn-danger flex-1"
            disabled={busy}
            onClick={() => void cancel()}
          >
            Да, отменить
          </button>
          <button
            type="button"
            className="btn-ghost flex-1"
            onClick={() => setConfirmCancel(false)}
          >
            Оставить
          </button>
        </div>
      </Modal>
    </div>
  )
}

export function OrdersList({ pendingOnly = false }: { pendingOnly?: boolean }) {
  const { ordersVersion } = useMini()
  const orders = useMiniApi<Order[]>('/api/v1/me/orders', [ordersVersion])

  if (orders.loading) return <Spinner label="Загружаем заказы…" />
  if (orders.error) return <ErrorState message={orders.error} onRetry={orders.reload} />

  const items = (orders.data ?? []).filter((order) => !pendingOnly || order.status === 'pending')
  if (!items.length) {
    return (
      <EmptyState
        title={pendingOnly ? 'Нет заказов на оплате' : 'Заказов пока нет'}
        text={pendingOnly ? 'Новые заказы появятся здесь.' : 'Выберите продукт в магазине.'}
      />
    )
  }

  return (
    <div className="space-y-3">
      {items.map((order) => (
        <OrderCard key={order.id} order={order} />
      ))}
    </div>
  )
}
