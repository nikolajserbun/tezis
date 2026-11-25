export function money(minor: number, currency = 'RUB'): string {
  const value = minor / 100
  const formatted = new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(value)
  return currency === 'RUB' ? `${formatted} ₽` : `${formatted} ${currency}`
}

export function compactMoney(minor: number): string {
  const value = minor / 100
  if (Math.abs(value) >= 1_000_000) {
    return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(value / 1_000_000)} млн ₽`
  }
  if (Math.abs(value) >= 10_000) {
    return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(value / 1000)} тыс. ₽`
  }
  return money(minor)
}

export function date(value: string | null | undefined, withTime = false): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  }).format(parsed)
}

export function shortId(value: string | null | undefined): string {
  if (!value) return '—'
  return value.slice(0, 8)
}

/** Telegram-formatted generation text as readable plain text for the Mini App. */
export function plainText(value: string): string {
  return value
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|li)>/gi, '\n')
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&')
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидает',
  paid: 'Оплачен',
  canceled: 'Отменён',
  refunded: 'Возвращён',
  expired: 'Истёк',
  active: 'Активен',
  canceled_by_user: 'Отменён',
  succeeded: 'Успешно',
  failed: 'Ошибка',
  refunded_by_admin: 'Возвращён',
  sent: 'Отправлена',
  scheduled: 'Запланирована',
  draft: 'Черновик',
  processing: 'В обработке',
  open: 'Открыт',
  closed: 'Закрыт',
  approved: 'Одобрена',
  rejected: 'Отклонена',
  new: 'Новый',
}

export function statusLabel(value: string): string {
  return STATUS_LABELS[value] ?? value
}

export function statusTone(value: string): 'green' | 'gold' | 'red' | 'neutral' {
  if (['paid', 'active', 'succeeded', 'sent', 'closed', 'approved'].includes(value)) return 'green'
  if (['pending', 'scheduled', 'processing', 'open', 'new'].includes(value)) return 'gold'
  if (['canceled', 'canceled_by_user', 'refunded', 'expired', 'failed', 'rejected'].includes(value)) return 'red'
  return 'neutral'
}

export function plural(count: number, forms: [string, string, string]): string {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return forms[0]
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1]
  return forms[2]
}

export function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(text).then(() => true).catch(() => false)
  }
  return Promise.resolve(false)
}
