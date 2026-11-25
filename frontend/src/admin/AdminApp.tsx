import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiRequest, getToken, setToken, type Role, type User } from '../lib/api'
import { Spinner, Toast } from '../components/ui'
import Login from './Login'
import DashboardSection from './Dashboard'
import UsersSection from './Users'
import ProductsSection from './Products'
import OrdersSection from './Orders'
import PaymentsSection from './Payments'
import SubscriptionsSection from './Subscriptions'
import BroadcastsSection from './Broadcasts'
import PayoutsSection from './Payouts'
import SupportSection from './Support'
import SettingsSection from './Settings'
import ExpensesSection from './Expenses'
import AuditSection from './Audit'
import { ROLE_LABELS, type Config, type SectionId } from './types'
import { useApi } from '../lib/api'

type Access = 'staff' | 'admin' | 'owner'

interface NavItem {
  id: SectionId
  label: string
  access: Access
}

const NAV: NavItem[] = [
  { id: 'dashboard', label: 'Обзор', access: 'staff' },
  { id: 'users', label: 'Пользователи', access: 'staff' },
  { id: 'products', label: 'Товары', access: 'staff' },
  { id: 'orders', label: 'Заказы', access: 'staff' },
  { id: 'payments', label: 'Платежи', access: 'staff' },
  { id: 'subscriptions', label: 'Подписки', access: 'staff' },
  { id: 'broadcasts', label: 'Рассылки', access: 'staff' },
  { id: 'payouts', label: 'Выплаты', access: 'staff' },
  { id: 'support', label: 'Поддержка', access: 'staff' },
  { id: 'settings', label: 'Настройки', access: 'admin' },
  { id: 'expenses', label: 'Расходы', access: 'admin' },
  { id: 'audit', label: 'Журнал', access: 'admin' },
]

function hasAccess(role: Role, access: Access): boolean {
  if (access === 'staff') return ['manager', 'admin', 'owner'].includes(role)
  if (access === 'admin') return ['admin', 'owner'].includes(role)
  return role === 'owner'
}

export default function AdminApp() {
  const config = useApi<Config>('/api/v1/auth/config')
  const [me, setMe] = useState<User | null>(null)
  const [checking, setChecking] = useState(() => Boolean(getToken()))
  const [authError, setAuthError] = useState('')
  const [toast, setToast] = useState('')
  const [section, setSection] = useState<SectionId>('dashboard')

  useEffect(() => {
    if (!getToken()) {
      setChecking(false)
      return
    }
    let alive = true
    apiRequest<User>('/api/v1/auth/me')
      .then((user) => {
        if (alive) setMe(user)
      })
      .catch((error: unknown) => {
        if (alive) {
          setToken(null)
          setAuthError(error instanceof Error ? error.message : 'Не удалось восстановить сессию')
        }
      })
      .finally(() => {
        if (alive) setChecking(false)
      })
    return () => {
      alive = false
    }
  }, [])

  const handleLogin = useCallback(async (token: string) => {
    setToken(token)
    try {
      const user = await apiRequest<User>('/api/v1/auth/me')
      setMe(user)
      setAuthError('')
    } catch (error) {
      setToken(null)
      throw error
    }
  }, [])

  async function handleLogout() {
    try {
      await apiRequest('/api/v1/auth/logout', { method: 'POST' })
    } catch {
      setToast('Не удалось завершить сессию на сервере')
    }
    setToken(null)
    setMe(null)
    setSection('dashboard')
  }

  const role: Role = me?.role ?? 'user'
  const isAdmin = role === 'admin' || role === 'owner'
  const isOwner = role === 'owner'
  const visibleNav = useMemo(() => NAV.filter((item) => hasAccess(role, item.access)), [role])

  useEffect(() => {
    if (!visibleNav.some((item) => item.id === section)) setSection('dashboard')
  }, [visibleNav, section])

  const navButtons = visibleNav.map((item) => (
    <button
      key={item.id}
      type="button"
      onClick={() => setSection(item.id)}
      className={`nav-link whitespace-nowrap ${section === item.id ? 'nav-link-active' : ''}`}
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${section === item.id ? 'bg-gold-400' : 'bg-ivory/30'}`} />
      {item.label}
    </button>
  ))

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ivory">
        <Spinner label="Проверяем сессию…" />
      </div>
    )
  }

  if (!me) {
    const fallbackConfig: Config = { app_name: 'Тезис', bot_username: '', app_env: 'prod' }
    return (
      <>
        {config.error && (
          <div className="bg-red-50 px-4 py-2 text-center text-sm text-red-700">
            Не удалось загрузить конфигурацию: {config.error}
          </div>
        )}
        {authError && (
          <div className="bg-gold-100 px-4 py-2 text-center text-sm text-gold-700">{authError}</div>
        )}
        <Login config={config.data ?? (config.error ? fallbackConfig : null)} onLogin={handleLogin} />
      </>
    )
  }

  if (!hasAccess(role, 'staff')) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ivory px-4">
        <div className="card max-w-md p-8 text-center">
          <h1 className="font-display text-2xl font-semibold">Недостаточно прав</h1>
          <p className="mt-3 text-sm text-ink-600">
            У вас роль «{ROLE_LABELS[role] ?? role}». Для входа в панель нужна роль менеджера,
            администратора или владельца.
          </p>
          <button type="button" className="btn-primary mt-6 w-full" onClick={() => void handleLogout()}>
            Выйти
          </button>
        </div>
      </div>
    )
  }

  function renderSection() {
    switch (section) {
      case 'dashboard': return <DashboardSection />
      case 'users': return <UsersSection canManage={isAdmin} isOwner={isOwner} />
      case 'products': return <ProductsSection canManage={isAdmin} />
      case 'orders': return <OrdersSection canManage={isAdmin} />
      case 'payments': return <PaymentsSection />
      case 'subscriptions': return <SubscriptionsSection canManage={isAdmin} />
      case 'broadcasts': return <BroadcastsSection />
      case 'payouts': return <PayoutsSection canManage={isAdmin} />
      case 'support': return <SupportSection />
      case 'settings': return isAdmin ? <SettingsSection isOwner={isOwner} /> : null
      case 'expenses': return isAdmin ? <ExpensesSection /> : null
      case 'audit': return isAdmin ? <AuditSection /> : null
    }
  }

  return (
    <div className="min-h-screen bg-ivory">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col bg-ink-950 px-4 py-6 lg:flex">
        <div className="mb-8 px-2">
          <p className="font-display text-2xl font-semibold text-ivory">Тезис</p>
          <p className="text-xs text-ivory/50">Панель управления</p>
        </div>
        <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-ivory/40">
          Разделы
        </p>
        <nav className="flex flex-col gap-1">{navButtons}</nav>
        <div className="mt-auto border-t border-white/10 pt-4">
          <p className="px-2 text-sm text-ivory">{me.first_name}</p>
          <p className="px-2 text-xs text-ivory/50">{ROLE_LABELS[role] ?? role}</p>
          <button type="button" className="nav-link mt-3 w-full" onClick={() => void handleLogout()}>
            Выйти
          </button>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 bg-ink-950 px-4 py-3 lg:hidden">
          <div className="flex items-center justify-between gap-3">
            <div>
              <span className="font-display text-lg text-ivory">Тезис</span>
              <span className="ml-2 text-xs text-ivory/40">админка</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="badge-gold">{ROLE_LABELS[role] ?? role}</span>
              <button type="button" className="text-sm text-ivory/80" onClick={() => void handleLogout()}>
                Выйти
              </button>
            </div>
          </div>
          <nav className="no-scrollbar -mx-4 mt-3 flex gap-2 overflow-x-auto px-4 pb-1">
            {navButtons}
          </nav>
        </header>

        <main className="safe-bottom mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          {renderSection()}
        </main>
      </div>

      <Toast message={toast} onClose={() => setToast('')} />
    </div>
  )
}
