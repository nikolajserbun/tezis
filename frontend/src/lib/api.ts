const TOKEN_KEY = 'tezis_token'
const API_BASE = import.meta.env.VITE_API_BASE || ''

export class ApiError extends Error {
  status: number
  code: string
  details: unknown

  constructor(status: number, message: string, code = 'error', details: unknown = null) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage может быть недоступен в webview */
  }
}

interface RequestOptions {
  method?: string
  body?: unknown
  auth?: boolean
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true } = options
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      credentials: 'include',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Нет связи с сервером. Проверьте подключение.', 'network_error')
  }

  if (response.status === 204) return undefined as T

  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text()

  if (!response.ok) {
    if (response.status === 401) setToken(null)
    const message =
      (payload && typeof payload === 'object' && 'message' in payload
        ? String((payload as { message: unknown }).message)
        : null) ||
      (typeof payload === 'string' && payload) ||
      `Ошибка ${response.status}`
    const code =
      payload && typeof payload === 'object' && 'error' in payload
        ? String((payload as { error: unknown }).error)
        : 'error'
    throw new ApiError(response.status, message, code, payload)
  }

  return payload as T
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Role = 'user' | 'manager' | 'admin' | 'owner'

export interface User {
  id: string
  tg_id: number
  username: string | null
  first_name: string
  last_name: string | null
  language: string
  role: Role
  referral_code: string
  balance_minor: number
  neurons_bonus: number
  neurons_limit_override: number | null
  is_blocked: boolean
  onboarding_completed: boolean
  created_at: string
}

export interface BrandProfile {
  niche: string
  audience: string
  tone: string
  goals: string
  taboos: string
}

export interface Usage {
  has_subscription: boolean
  plan_title: string | null
  neurons_limit: number
  neurons_used: number
  neurons_left: number
  // Next weekly refill; null means the free lifetime budget never refreshes.
  resets_at: string | null
  expires_at: string | null
}

export interface Me {
  user: User
  brand: BrandProfile | null
  usage: Usage
}

export interface Product {
  id: string
  slug: string
  title: string
  description: string
  kind: 'digital' | 'subscription'
  price_minor: number
  currency: string
  price_stars: number | null
  duration_days: number | null
  neurons_per_week: number
  brand_limit: number
  file_key: string | null
  cover_url: string | null
  features: string[]
  is_active: boolean
  sort_order: number
}

export interface OrderItem {
  id: string
  product_id: string | null
  title: string
  kind: string
  unit_price_minor: number
  unit_price_stars: number
  quantity: number
  total_minor: number
  total_stars: number
}

export interface Payment {
  id: string
  provider: string
  provider_payment_id: string
  telegram_charge_id: string | null
  amount_minor: number
  amount_stars: number
  currency: string
  status: string
  created_at: string
}

export interface Order {
  id: string
  status: string
  subtotal_minor: number
  discount_minor: number
  total_minor: number
  total_stars: number
  currency: string
  created_at: string
  paid_at: string | null
  fulfilled_at: string | null
  items: OrderItem[]
  payments: Payment[]
}

export interface Subscription {
  id: string
  user_id: string
  product_id: string
  product_title: string | null
  status: string
  started_at: string
  current_period_start: string
  current_period_end: string
  expires_at: string
  auto_renew: boolean
  neurons_per_week: number
  neurons_limit: number
  neurons_used: number
  source_order_id: string | null
}

export interface Generation {
  id: string
  kind: string
  platform: string
  topic: string
  result: string
  is_saved: boolean
  tokens: number
  cost_minor: number
  created_at: string
}

export interface ChatSource {
  title: string
  url: string
  snippet: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: ChatSource[]
  demo_mode: boolean
  created_at: string
}

export interface ChatAnswer {
  id: string
  role: 'assistant'
  answer: string
  sources: ChatSource[]
  demo_mode: boolean
  tokens: number
  cost_minor: number
  neurons_left: number
  created_at: string
}

export interface ReferralStats {
  code: string
  link: string
  invited_count: number
  activated_count: number
  earned_minor: number
  pending_minor: number
  balance_minor: number
  bonus_minor: number
}

export interface Payout {
  id: string
  user_id: string
  amount_minor: number
  method: string
  requisites: string
  status: string
  admin_note: string | null
  created_at: string
  processed_at: string | null
}

export interface SupportMessage {
  id: string
  author_type: string
  text: string
  created_at: string
}

export interface SupportTicket {
  id: string
  user_id: string
  subject: string
  status: string
  priority: string
  created_at: string
  updated_at: string
  messages: SupportMessage[]
}

export interface Broadcast {
  id: string
  title: string
  text: string
  segment: Record<string, unknown>
  status: string
  scheduled_at: string | null
  sent_count: number
  failed_count: number
  created_at: string
}

export interface Expense {
  id: string
  category: string
  amount_minor: number
  currency: string
  spent_at: string
  note: string
  created_at: string
}

export interface AuditLog {
  id: string
  actor_id: string | null
  action: string
  entity_type: string
  entity_id: string | null
  payload: Record<string, unknown>
  ip: string | null
  created_at: string
}

export interface Setting {
  key: string
  value: unknown
  updated_at: string | null
}

export interface TopProduct {
  title: string
  revenue_minor: number
  orders_count: number
}

export interface DailyPoint {
  day: string
  revenue_minor: number
  users: number
}

export interface Dashboard {
  total_users: number
  new_users_30d: number
  buyers: number
  revenue_30d_minor: number
  refunds_30d_minor: number
  expenses_30d_minor: number
  ai_cost_30d_minor: number
  profit_30d_minor: number
  mrr_minor: number
  arpu_minor: number
  active_subscriptions: number
  pending_payouts: number
  open_tickets: number
  recent_orders: Order[]
  top_products: TopProduct[]
  daily: DailyPoint[]
}

export interface Invoice {
  order_id: string
  invoice_url: string
  total_stars: number
  total_minor: number
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

import { useCallback, useEffect, useState } from 'react'

export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(Boolean(path))
  const [tick, setTick] = useState(0)

  const reload = useCallback(() => setTick((value) => value + 1), [])

  // A new session/endpoint must never render the previous account's data.
  // Do not clear on `tick`: that is an explicit reload of the same endpoint.
  useEffect(() => {
    setData(null)
  }, [path])

  useEffect(() => {
    if (!path) {
      setLoading(false)
      return
    }
    let alive = true
    setLoading(true)
    setError(null)
    apiRequest<T>(path)
      .then((result) => {
        if (alive) setData(result)
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : 'Не удалось загрузить данные')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps])

  return { data, error, loading, reload, setData }
}
