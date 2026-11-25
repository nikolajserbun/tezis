import type { Role } from '../lib/api'

export type SectionId =
  | 'dashboard'
  | 'users'
  | 'products'
  | 'orders'
  | 'payments'
  | 'subscriptions'
  | 'broadcasts'
  | 'payouts'
  | 'support'
  | 'settings'
  | 'expenses'
  | 'audit'

export interface Config {
  app_name: string
  bot_username: string
  app_env: string
}

export interface TelegramLoginPayload {
  id: number
  first_name?: string
  last_name?: string
  username?: string
  photo_url?: string
  auth_date: number
  hash: string
}

export interface ReferralEarning {
  id: string
  referrer_id: string
  referrer_tg_id: number
  amount_minor: number
  rate_bp: number
  source: string
  status: string
  created_at: string
}

export const ROLES: Role[] = ['user', 'manager', 'admin', 'owner']

export const ROLE_LABELS: Record<Role, string> = {
  user: 'Пользователь',
  manager: 'Менеджер',
  admin: 'Администратор',
  owner: 'Владелец',
}

declare global {
  interface Window {
    onTelegramAuth?: (user: TelegramLoginPayload) => void
  }
}
