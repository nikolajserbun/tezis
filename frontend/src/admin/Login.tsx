import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiRequest, type TokenResponse } from '../lib/api'
import { Field, Spinner } from '../components/ui'
import type { Config, TelegramLoginPayload } from './types'
import type { TelegramWebAppWindow } from '../mini/types'

export default function Login({
  config,
  onLogin,
}: {
  config: Config | null
  onLogin: (token: string) => Promise<void>
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const widgetRef = useRef<HTMLDivElement | null>(null)
  const onLoginRef = useRef(onLogin)
  const bot = config?.bot_username?.trim() ?? ''

  useEffect(() => {
    onLoginRef.current = onLogin
  }, [onLogin])

  useEffect(() => {
    const initData = (window as TelegramWebAppWindow).Telegram?.WebApp?.initData?.trim()
    if (!initData) return
    let disposed = false
    setBusy(true)
    void (async () => {
      try {
        const result = await apiRequest<TokenResponse>('/api/v1/auth/miniapp', {
          method: 'POST',
          body: { init_data: initData },
        })
        if (disposed) return
        if (result.user.role !== 'owner') {
          setError('Доступ к админ-панели есть только у владельца.')
          return
        }
        await onLoginRef.current(result.access_token)
      } catch (err) {
        if (!disposed) {
          setError(err instanceof Error ? err.message : 'Не удалось войти через Telegram')
        }
      } finally {
        if (!disposed) setBusy(false)
      }
    })()
    return () => {
      disposed = true
    }
  }, [])

  useEffect(() => {
    if (!bot) return

    const callback = (user: TelegramLoginPayload) => {
      setError('')
      setBusy(true)
      void (async () => {
        try {
          const result = await apiRequest<TokenResponse>('/api/v1/auth/telegram', {
            method: 'POST',
            body: user,
          })
          await onLoginRef.current(result.access_token)
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Не удалось войти через Telegram')
        } finally {
          setBusy(false)
        }
      })()
    }

    window.onTelegramAuth = callback
    let disposed = false
    const timer = window.setTimeout(() => {
      const container = widgetRef.current
      if (disposed || !container || container.querySelector('script[data-telegram-login]')) return
      const script = document.createElement('script')
      script.async = true
      script.src = 'https://telegram.org/js/telegram-widget.js?22'
      script.dataset.telegramLogin = bot
      script.dataset.size = 'large'
      script.dataset.onauth = 'onTelegramAuth(user)'
      container.replaceChildren(script)
    }, 0)

    return () => {
      disposed = true
      window.clearTimeout(timer)
      if (window.onTelegramAuth === callback) delete window.onTelegramAuth
    }
  }, [bot])

  async function handleDev(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const result = await apiRequest<TokenResponse>('/api/v1/auth/dev', {
        method: 'POST',
        body: { email, password },
      })
      await onLogin(result.access_token)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось войти')
    } finally {
      setBusy(false)
    }
  }

  if (!config) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ivory px-4">
        <div className="w-full max-w-md">
          <Spinner label="Загружаем конфигурацию…" />
        </div>
      </div>
    )
  }

  const devEnabled = config.app_env !== 'prod'

  return (
    <div className="flex min-h-screen items-center justify-center bg-ivory px-4 py-10">
      <div className="w-full max-w-4xl">
        <div className="mb-8 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-gold-600">
            Панель управления
          </p>
          <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight text-ink-900 sm:text-5xl">
            {config.app_name || 'Тезис'}
          </h1>
          <p className="mt-3 text-sm text-ink-500">Войдите, чтобы управлять студией и продажами.</p>
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <section className="card p-6">
            <h2 className="font-display text-xl font-semibold">Вход через Telegram</h2>
            <p className="hint mt-2">Используйте аккаунт, которому выданы права администратора.</p>
            <div ref={widgetRef} className="mt-6 flex min-h-[60px] items-center justify-center">
              {bot ? (
                <span className="hint">Загружаем кнопку входа…</span>
              ) : (
                <span className="hint">Бот для входа не настроен на сервере.</span>
              )}
            </div>
          </section>

          {devEnabled && (
            <section className="card p-6">
              <h2 className="font-display text-xl font-semibold">Локальный вход</h2>
              <p className="hint mt-2">Локальный режим: доступен только вне production.</p>
              <form onSubmit={handleDev} className="mt-5 space-y-4">
                <Field label="Email">
                  <input
                    className="input"
                    type="email"
                    autoComplete="username"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                  />
                </Field>
                <Field label="Пароль">
                  <input
                    className="input"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                  />
                </Field>
                <button type="submit" className="btn-primary w-full" disabled={busy}>
                  {busy ? 'Входим…' : 'Войти'}
                </button>
              </form>
            </section>
          )}
        </div>

        {error && <p className="mt-5 text-center text-sm text-red-700">{error}</p>}
        <p className="hint mt-8 text-center">
          Окружение: {config.app_env || 'не указано'}
          {!devEnabled && ' · вход по email/паролю отключён'}
        </p>
      </div>
    </div>
  )
}
