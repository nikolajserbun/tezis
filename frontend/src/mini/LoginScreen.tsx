import { useState } from 'react'
import type { FormEvent } from 'react'
import { ErrorState, Field } from '../components/ui'
import { openExternal } from './telegram'
import type { Config } from './types'

export function LoginScreen({
  config,
  message,
  onDevLogin,
  onTelegramLogin,
}: {
  config: Config
  message: string | null
  onDevLogin: (email: string, password: string) => Promise<void>
  onTelegramLogin?: (() => Promise<void>) | null
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const isDev = config.app_env !== 'prod'

  const submit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    if (busy || !email.trim() || !password) return
    setBusy(true)
    try {
      await onDevLogin(email.trim(), password)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-5 py-10">
      <div className="flex items-center gap-3">
        <span className="mini-brand-dot h-2.5 w-2.5 rounded-full bg-gold-400" aria-hidden />
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gold-600">
          AI-студия эксперта
        </p>
      </div>
      <h1 className="mt-3 font-display text-4xl font-semibold leading-tight tracking-tight text-ink-900">
        Тезис
      </h1>
      <p className="mt-3 max-w-sm text-sm leading-relaxed text-ink-600">
        Войдите, чтобы собрать профиль бренда, создавать тексты и управлять подпиской.
      </p>

      <div className="mini-reveal mt-8 space-y-4" style={{ animationDelay: '80ms' }}>
        {message && <ErrorState message={message} />}

        {onTelegramLogin && (
          <button type="button" className="btn-gold w-full" onClick={() => void onTelegramLogin()}>
            {message ? 'Повторить вход через Telegram' : 'Войти через Telegram'}
          </button>
        )}

        {isDev ? (
          <form className="card space-y-4 p-5" onSubmit={(event) => void submit(event)}>
            <div>
              <p className="font-display text-xl font-semibold text-ink-900">Локальный вход</p>
              <p className="hint mt-1">Локальный демо-режим — доступен только вне продакшена.</p>
            </div>
            <Field label="Email">
              <input
                className="input"
                type="email"
                autoComplete="username"
                placeholder="owner@test.local"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>
            <Field label="Пароль">
              <input
                className="input"
                type="password"
                autoComplete="current-password"
                placeholder="test-password-123"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>
            <button
              type="submit"
              className="btn-primary w-full"
              disabled={busy || !email.trim() || !password}
            >
              {busy ? 'Входим…' : 'Войти в демо-режиме'}
            </button>
          </form>
        ) : (
          <div className="card p-5">
            <p className="font-display text-xl font-semibold text-ink-900">Нужен Telegram</p>
            <p className="mt-2 text-sm leading-relaxed text-ink-600">
              Вход доступен только из Mini App. Откройте приложение через бота.
            </p>
            {config.bot_username && (
              <button
                type="button"
                className="btn-gold mt-4 w-full"
                onClick={() => openExternal(`https://t.me/${config.bot_username}`)}
              >
                Открыть бота
              </button>
            )}
          </div>
        )}
      </div>
    </main>
  )
}
