import { useCallback, useEffect, useRef, useState } from 'react'
import { Toast } from '../components/ui'
import { ApiError, apiRequest, getToken, setToken, useApi } from '../lib/api'
import type { Me, TokenResponse } from '../lib/api'
import { plural } from '../lib/format'
import { MiniContext } from './context'
import type { MiniContextValue, MiniRequestOptions } from './context'
import { HomeScreen } from './HomeScreen'
import { LoginScreen } from './LoginScreen'
import { OrdersScreen } from './OrdersScreen'
import { ChatScreen } from './ChatScreen'
import { BootView, TabIcon } from './parts'
import { ProfileScreen } from './ProfileScreen'
import { ShopScreen } from './ShopScreen'
import { StudioScreen } from './StudioScreen'
import { bindBackButton, getInitData, haptic, initTelegram } from './telegram'
import type { Config, Tab, TabFocus } from './types'

type AuthState = 'boot' | 'loading' | 'ready' | 'guest'

const TABS: { tab: Tab; label: string }[] = [
  { tab: 'home', label: 'Главная' },
  { tab: 'studio', label: 'Студия' },
  { tab: 'chat', label: 'Чат' },
  { tab: 'shop', label: 'Магазин' },
  { tab: 'orders', label: 'Заказы' },
  { tab: 'profile', label: 'Профиль' },
]

export default function MiniApp() {
  const [authState, setAuthState] = useState<AuthState>('boot')
  const [authMessage, setAuthMessage] = useState<string | null>(null)
  const [sessionKey, setSessionKey] = useState(0)
  const [meVersion, setMeVersion] = useState(0)
  const [ordersVersion, setOrdersVersion] = useState(0)
  const [toast, setToast] = useState('')
  const [history, setHistory] = useState<Tab[]>(['home'])
  const [focus, setFocus] = useState<TabFocus>(null)
  const authStarted = useRef(false)

  const configQuery = useApi<Config>('/api/v1/auth/config')
  const meQuery = useApi<Me>(authState === 'ready' ? '/api/v1/me' : null, [
    sessionKey,
    meVersion,
  ])

  const config: Config = configQuery.data ?? {
    app_name: 'Тезис',
    bot_username: '',
    app_env: 'dev',
  }
  const tab = history[history.length - 1]
  const hasTelegramInitData = Boolean(getInitData())

  const notify = useCallback((message: string): void => setToast(message), [])
  const dismissToast = useCallback((): void => setToast(''), [])

  const signOut = useCallback((): void => {
    setToken(null)
    setAuthState('guest')
    setAuthMessage(null)
    setSessionKey((value) => value + 1)
    setHistory(['home'])
    setFocus(null)
  }, [])

  const handleApiError = useCallback(
    (error: unknown): void => {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : 'Не удалось выполнить действие'
      notify(message)
      if (error instanceof ApiError && error.status === 401) signOut()
    },
    [notify, signOut],
  )

  const handleLoadError = useCallback(
    (_message: string): void => {
      if (!getToken()) signOut()
    },
    [signOut],
  )

  const run = useCallback(
    async <T,>(path: string, options: MiniRequestOptions = {}): Promise<T | null> => {
      haptic()
      try {
        return await apiRequest<T>(path, options)
      } catch (error) {
        handleApiError(error)
        return null
      }
    },
    [handleApiError],
  )

  const refreshMe = useCallback((): void => {
    haptic()
    setMeVersion((value) => value + 1)
  }, [])

  const bumpOrders = useCallback((): void => setOrdersVersion((value) => value + 1), [])

  const go = useCallback((next: Tab, nextFocus: TabFocus = null): void => {
    haptic()
    setHistory((current) => (current[current.length - 1] === next ? current : [...current, next]))
    setFocus(nextFocus)
  }, [])

  const back = useCallback((): void => {
    setHistory((current) => (current.length > 1 ? current.slice(0, -1) : current))
    setFocus(null)
  }, [])

  const focusHandled = useCallback((): void => setFocus(null), [])

  const loginWithTelegram = useCallback(async (): Promise<void> => {
    const initData = getInitData()
    if (!initData) return
    setAuthState('loading')
    haptic()
    try {
      const response = await apiRequest<TokenResponse>('/api/v1/auth/miniapp', {
        method: 'POST',
        body: { init_data: initData },
        auth: false,
      })
      setToken(response.access_token)
      setAuthState('ready')
      setAuthMessage(null)
      setSessionKey((value) => value + 1)
    } catch (error) {
      setToken(null)
      handleApiError(error)
      setAuthMessage(error instanceof Error ? error.message : 'Не удалось войти через Telegram')
      setAuthState('guest')
    }
  }, [handleApiError])

  const devLogin = useCallback(
    async (email: string, password: string): Promise<void> => {
      haptic()
      try {
        const response = await apiRequest<TokenResponse>('/api/v1/auth/dev', {
          method: 'POST',
          body: { email, password },
          auth: false,
        })
        setToken(response.access_token)
        setAuthState('ready')
        setAuthMessage(null)
        setSessionKey((value) => value + 1)
        notify('Вы вошли в демо-режиме')
      } catch (error) {
        handleApiError(error)
      }
    },
    [handleApiError, notify],
  )

  useEffect(() => {
    initTelegram()
  }, [])

  useEffect(() => {
    if (!configQuery.data || authStarted.current) return
    authStarted.current = true

    const bootstrap = (): void => {
      if (getInitData()) {
        void loginWithTelegram()
        return
      }
      if (getToken()) {
        setAuthState('ready')
        setSessionKey((value) => value + 1)
      } else {
        setAuthState('guest')
      }
    }

    bootstrap()
  }, [configQuery.data, loginWithTelegram])

  useEffect(() => {
    if (meQuery.error && !getToken()) signOut()
  }, [meQuery.error, signOut])

  useEffect(() => bindBackButton(history.length > 1, back), [history.length, back])

  let content
  if (!configQuery.data && configQuery.loading) {
    content = <BootView label="Загружаем приложение…" />
  } else if (configQuery.error) {
    content = <BootView label="Загружаем приложение…" error={configQuery.error} onRetry={configQuery.reload} />
  } else if (authState === 'boot' || authState === 'loading') {
    content = <BootView label="Подключаемся к Telegram…" />
  } else if (authState === 'guest') {
    content = (
      <LoginScreen
        config={config}
        message={authMessage}
        onDevLogin={devLogin}
        onTelegramLogin={hasTelegramInitData ? loginWithTelegram : null}
      />
    )
  } else if (!meQuery.data) {
    content = (
      <BootView
        label="Загружаем профиль…"
        error={meQuery.error}
        onRetry={meQuery.reload}
      />
    )
  } else {
    const me = meQuery.data
    const contextValue: MiniContextValue = {
      config,
      me,
      isDev: config.app_env !== 'prod',
      ordersVersion,
      notify,
      haptic,
      run,
      refreshMe,
      bumpOrders,
      go,
      signOut,
      handleApiError,
      handleLoadError,
    }

    content = (
      <MiniContext.Provider value={contextValue}>
        <div className="min-h-screen bg-ivory">
          <header className="sticky top-0 z-30 border-b border-ink-100 bg-ivory/90 backdrop-blur">
            <div className="mx-auto flex w-full max-w-md items-center justify-between gap-3 px-4 py-3">
              <div className="flex items-center gap-2.5">
                <span className="font-display text-xl font-semibold tracking-tight text-ink-900">
                  Тезис
                </span>
                <span className="h-1.5 w-1.5 rounded-full bg-gold-400" aria-hidden />
              </div>
              <div className="text-right">
                <p className="text-xs font-medium text-ink-900">
                  {me.usage.plan_title || 'Бесплатный доступ'}
                </p>
                <p className="hint">
                  Осталось {me.usage.generations_left}{' '}
                  {plural(me.usage.generations_left, ['генерация', 'генерации', 'генераций'])}
                </p>
              </div>
            </div>
          </header>

          <main
            className="mx-auto w-full max-w-md px-4 pt-5"
            style={{ paddingBottom: 'calc(6.5rem + env(safe-area-inset-bottom))' }}
          >
            {tab === 'home' && <HomeScreen />}
            {tab === 'studio' && <StudioScreen />}
            {tab === 'chat' && <ChatScreen />}
            {tab === 'shop' && <ShopScreen />}
            {tab === 'orders' && <OrdersScreen />}
            {tab === 'profile' && (
              <ProfileScreen focus={focus} onFocusHandled={focusHandled} />
            )}
          </main>

          <nav
            className="safe-bottom fixed inset-x-0 bottom-0 z-40 mx-auto w-full max-w-md border-t border-ink-100 bg-ivory/95 backdrop-blur"
            aria-label="Разделы"
          >
            <div className="grid grid-cols-6 gap-1 px-2 pt-2">
              {TABS.map((item) => {
                const active = item.tab === tab
                return (
                  <button
                    key={item.tab}
                    type="button"
                    aria-current={active ? 'page' : undefined}
                    className={`flex flex-col items-center gap-1 rounded-xl py-1.5 text-[10px] font-medium transition ${
                      active ? 'text-gold-700' : 'text-ink-500 hover:text-ink-800'
                    }`}
                    onClick={() => go(item.tab)}
                  >
                    <TabIcon tab={item.tab} />
                    <span>{item.label}</span>
                  </button>
                )
              })}
            </div>
          </nav>
        </div>
      </MiniContext.Provider>
    )
  }

  return (
    <>
      {content}
      <div className="[&>div]:bottom-24">
        <Toast message={toast} onClose={dismissToast} />
      </div>
    </>
  )
}
