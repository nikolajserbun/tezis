import type { ReactNode } from 'react'
import { statusTone } from '../lib/format'

export function Spinner({ label = 'Загружаем…' }: { label?: string }) {
  return (
    <div className="flex min-h-[180px] items-center justify-center gap-3 text-sm text-ink-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-200 border-t-gold-400" />
      {label}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card-muted flex flex-col items-start gap-3 p-5">
      <p className="text-sm text-red-700">{message}</p>
      {onRetry && (
        <button type="button" className="btn-ghost btn-sm" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, text }: { title: string; text?: string }) {
  return (
    <div className="card-muted p-8 text-center">
      <p className="font-medium text-ink-800">{title}</p>
      {text && <p className="mt-1 text-sm text-ink-500">{text}</p>}
    </div>
  )
}

export function Badge({ value }: { value: string }) {
  const tone = statusTone(value)
  const className = {
    green: 'badge-green',
    gold: 'badge-gold',
    red: 'badge-red',
    neutral: 'badge-neutral',
  }[tone]
  const label = {
    pending: 'Ожидает',
    paid: 'Оплачен',
    canceled: 'Отменён',
    refunded: 'Возвращён',
    expired: 'Истёк',
    active: 'Активен',
    succeeded: 'Успешно',
    failed: 'Ошибка',
    sent: 'Отправлена',
    scheduled: 'Запланирована',
    draft: 'Черновик',
    processing: 'В обработке',
    open: 'Открыт',
    closed: 'Закрыт',
    approved: 'Одобрена',
    rejected: 'Отклонена',
    new: 'Новый',
  }[value] ?? value
  return <span className={className}>{label}</span>
}

export function StatCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string
  value: ReactNode
  hint?: string
  accent?: boolean
}) {
  return (
    <div className={`card p-5 ${accent ? 'border-gold-200 bg-gold-100/30' : ''}`}>
      <p className="label">{label}</p>
      <p className="font-display text-2xl font-semibold tracking-tight text-ink-900">{value}</p>
      {hint && <p className="hint mt-1.5">{hint}</p>}
    </div>
  )
}

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="section-title">{title}</h1>
        {subtitle && <p className="mt-1.5 text-sm text-ink-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="hint mt-1 block">{hint}</span>}
    </label>
  )
}

export function Modal({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink-950/50 p-0 sm:items-center sm:p-6" role="dialog" aria-modal="true">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-2xl">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="font-display text-xl font-semibold">{title}</h2>
          <button type="button" className="btn-ghost btn-sm" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  if (!message) return null
  return (
    <div className="fixed bottom-5 left-1/2 z-[60] flex -translate-x-1/2 items-center gap-3 rounded-xl bg-ink-900 px-4 py-3 text-sm text-ivory shadow-lg">
      <span>{message}</span>
      <button type="button" onClick={onClose} className="text-ivory/60 hover:text-ivory" aria-label="Скрыть">
        ✕
      </button>
    </div>
  )
}
