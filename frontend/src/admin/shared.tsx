import { useCallback, useState, type ReactNode } from 'react'
import { apiRequest } from '../lib/api'
import { statusLabel, statusTone } from '../lib/format'
import { EmptyState, ErrorState, Spinner, Toast } from '../components/ui'

interface MutationOptions {
  method?: string
  body?: unknown
}

export function useAdminActions() {
  const [toast, setToast] = useState('')
  const [busy, setBusy] = useState(false)

  const notify = useCallback((message: string) => setToast(message), [])
  const hideToast = useCallback(() => setToast(''), [])

  const run = useCallback(
    async <T,>(path: string, options: MutationOptions = {}): Promise<T | null> => {
      setBusy(true)
      try {
        return await apiRequest<T>(path, options)
      } catch (error) {
        notify(error instanceof Error ? error.message : 'Не удалось выполнить действие')
        return null
      } finally {
        setBusy(false)
      }
    },
    [notify],
  )

  return { toast, notify, hideToast, busy, run }
}

export function DataState({
  loading,
  error,
  onRetry,
  empty,
  children,
}: {
  loading?: boolean
  error: string | null
  onRetry?: () => void
  empty?: boolean
  children: ReactNode
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />
  if (loading) return <Spinner />
  if (empty) return <EmptyState title="Ничего не найдено" text="Попробуйте изменить фильтры." />
  return <>{children}</>
}

export function Pagination({
  offset,
  limit,
  count,
  onOffset,
}: {
  offset: number
  limit: number
  count: number
  onOffset: (value: number) => void
}) {
  const hasPrev = offset > 0
  const hasNext = count >= limit
  if (!hasPrev && !hasNext) return null

  return (
    <div className="mt-4 flex items-center justify-between gap-3 border-t border-ink-100 pt-4">
      <span className="hint">Показано {count} записей</span>
      <div className="flex gap-2">
        <button
          type="button"
          className="btn-ghost btn-sm"
          disabled={!hasPrev}
          onClick={() => onOffset(Math.max(0, offset - limit))}
        >
          Назад
        </button>
        <button
          type="button"
          className="btn-ghost btn-sm"
          disabled={!hasNext}
          onClick={() => onOffset(offset + limit)}
        >
          Дальше
        </button>
      </div>
    </div>
  )
}

export function FilterTabs<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}) {
  return (
    <div className="no-scrollbar mb-5 flex gap-2 overflow-x-auto pb-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`whitespace-nowrap rounded-xl px-3.5 py-2 text-sm font-medium transition ${
            value === option.value
              ? 'bg-ink-900 text-ivory'
              : 'border border-ink-200 bg-white text-ink-600 hover:border-ink-300'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function RowActions({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap gap-2">{children}</div>
}

const STATUS_OVERRIDES: Record<string, string> = {
  fulfilled: 'Выполнен',
  answered: 'Отвечен',
  sending: 'Отправляется',
}

export function statusName(value: string): string {
  return STATUS_OVERRIDES[value] ?? statusLabel(value)
}

export function StatusPill({ value }: { value: string }) {
  const toneClass = {
    green: 'badge-green',
    gold: 'badge-gold',
    red: 'badge-red',
    neutral: 'badge-neutral',
  }[statusTone(value)]
  return <span className={toneClass}>{statusName(value)}</span>
}

export function ToastHost({ message, onClose }: { message: string; onClose: () => void }) {
  return <Toast message={message} onClose={onClose} />
}
