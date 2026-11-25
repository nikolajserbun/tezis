import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Badge, EmptyState, ErrorState, Field, Modal, PageHeader, Spinner } from '../components/ui'
import { date, money, plural, shortId } from '../lib/format'
import type { Payout, ReferralStats, Subscription, SupportTicket } from '../lib/api'
import { useMini, useMiniApi } from './context'
import { BlockTitle, CopyButton } from './parts'
import type { TabFocus } from './types'

const ROLE_LABELS: Record<string, string> = {
  user: 'Пользователь',
  manager: 'Менеджер',
  admin: 'Администратор',
  owner: 'Владелец',
}

export function ProfileScreen({
  focus,
  onFocusHandled,
}: {
  focus: TabFocus
  onFocusHandled: () => void
}) {
  const { me, config, run, notify, signOut, haptic, ordersVersion, refreshMe } = useMini()
  const referralRef = useRef<HTMLElement | null>(null)
  const [financeVersion, setFinanceVersion] = useState(0)
  const [supportVersion, setSupportVersion] = useState(0)
  const [amount, setAmount] = useState('')
  const [requisites, setRequisites] = useState('')
  const [payoutBusy, setPayoutBusy] = useState(false)
  const [ticketOpen, setTicketOpen] = useState(false)
  const [ticketSubject, setTicketSubject] = useState('')
  const [ticketMessage, setTicketMessage] = useState('')
  const [ticketBusy, setTicketBusy] = useState(false)
  const [activeTicket, setActiveTicket] = useState<SupportTicket | null>(null)
  const [ticketLoading, setTicketLoading] = useState(false)
  const [logoutOpen, setLogoutOpen] = useState(false)

  const subscription = useMiniApi<Subscription | null>('/api/v1/me/subscription', [ordersVersion])
  const referrals = useMiniApi<ReferralStats>('/api/v1/me/referrals', [financeVersion, ordersVersion])
  const payouts = useMiniApi<Payout[]>('/api/v1/me/payouts', [financeVersion])
  const tickets = useMiniApi<SupportTicket[]>('/api/v1/me/support', [supportVersion])

  useEffect(() => {
    if (focus === 'referrals') {
      referralRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      onFocusHandled()
    }
  }, [focus, onFocusHandled])

  const requestPayout = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    const amountMinor = Math.round(Number(amount) * 100)
    if (!Number.isFinite(amountMinor) || amountMinor < 100000) {
      notify('Минимальная сумма выплаты — 1000 ₽')
      return
    }
    if (requisites.trim().length < 3) {
      notify('Укажите реквизиты — минимум 3 символа')
      return
    }

    setPayoutBusy(true)
    const created = await run<Payout>('/api/v1/me/payouts', {
      method: 'POST',
      body: { amount_minor: amountMinor, method: 'manual', requisites: requisites.trim() },
    })
    setPayoutBusy(false)
    if (!created) return
    notify('Заявка на выплату создана')
    setAmount('')
    setRequisites('')
    setFinanceVersion((value) => value + 1)
    refreshMe()
  }

  const createTicket = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    const message = ticketMessage.trim()
    if (message.length < 2) return
    setTicketBusy(true)
    const created = await run<SupportTicket>('/api/v1/me/support', {
      method: 'POST',
      body: { subject: ticketSubject.trim() || 'Обращение', message },
    })
    setTicketBusy(false)
    if (!created) return
    notify('Обращение отправлено')
    setTicketOpen(false)
    setTicketSubject('')
    setTicketMessage('')
    setSupportVersion((value) => value + 1)
  }

  const openTicket = async (ticket: SupportTicket): Promise<void> => {
    setTicketLoading(true)
    const detail = await run<SupportTicket>(`/api/v1/me/support/${ticket.id}`)
    setTicketLoading(false)
    if (!detail) return
    setActiveTicket(detail)
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Профиль" subtitle="Ваш аккаунт, бонусы и поддержка." />

      <section className="card p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-display text-2xl font-semibold text-ink-900">
              {me.user.first_name}
              {me.user.last_name ? ` ${me.user.last_name}` : ''}
            </p>
            <p className="hint mt-1">{me.user.username ? `@${me.user.username}` : 'Без username'}</p>
          </div>
          <span className="badge-neutral">{ROLE_LABELS[me.user.role] ?? me.user.role}</span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 border-t border-ink-100 pt-4 text-sm">
          <div>
            <p className="label">Telegram ID</p>
            <p className="text-ink-800">{me.user.tg_id}</p>
          </div>
          <div>
            <p className="label">В «Тезисе» с</p>
            <p className="text-ink-800">{date(me.user.created_at)}</p>
          </div>
        </div>
      </section>

      <section>
        <BlockTitle>Подписка</BlockTitle>
        {subscription.loading ? (
          <Spinner label="Проверяем подписку…" />
        ) : subscription.error ? (
          <ErrorState message={subscription.error} onRetry={subscription.reload} />
        ) : subscription.data ? (
          <div className="card p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-display text-lg font-semibold text-ink-900">
                  {subscription.data.product_title || 'Подписка «Тезис»'}
                </p>
                <p className="hint mt-1">До {date(subscription.data.expires_at)}</p>
              </div>
              <Badge value={subscription.data.status} />
            </div>
            <div className="mt-4 flex items-center justify-between border-t border-ink-100 pt-4 text-sm">
              <span className="text-ink-500">Генераций</span>
              <span className="font-medium text-ink-900">
                {subscription.data.generations_used} / {subscription.data.generations_limit}
              </span>
            </div>
          </div>
        ) : (
          <EmptyState title="Активной подписки нет" text="Тарифы доступны в магазине." />
        )}
      </section>

      <section ref={referralRef}>
        <BlockTitle>Партнёрская программа</BlockTitle>
        {referrals.loading ? (
          <Spinner label="Загружаем статистику…" />
        ) : referrals.error ? (
          <ErrorState message={referrals.error} onRetry={referrals.reload} />
        ) : referrals.data ? (
          <div className="card space-y-4 p-5">
            <div className="flex items-end justify-between gap-3">
              <div>
                <p className="label">Баланс бонусов</p>
                <p className="font-display text-3xl font-semibold text-ink-900">
                  {money(referrals.data.balance_minor)}
                </p>
              </div>
              <span className="badge-gold">
                {money(referrals.data.bonus_minor)} за друга
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 border-y border-ink-100 py-4">
              <div>
                <p className="label">Приглашено</p>
                <p className="text-lg font-medium text-ink-900">
                  {referrals.data.invited_count}{' '}
                  {plural(referrals.data.invited_count, ['человек', 'человека', 'человек'])}
                </p>
              </div>
              <div>
                <p className="label">Сделали запрос</p>
                <p className="text-lg font-medium text-ink-900">
                  {referrals.data.activated_count}
                </p>
              </div>
              <div>
                <p className="label">Заработано</p>
                <p className="text-sm font-medium text-ink-900">{money(referrals.data.earned_minor)}</p>
              </div>
              <div>
                <p className="label">Ожидает</p>
                <p className="text-sm font-medium text-ink-900">{money(referrals.data.pending_minor)}</p>
              </div>
            </div>
            <p className="hint">
              Бонус начисляется один раз, когда приглашённый друг сделает первый запрос
              в чате или студии.
            </p>
            <div>
              <p className="label">Ваш код</p>
              <div className="flex items-center justify-between gap-3">
                <span className="truncate font-medium text-ink-900">{referrals.data.code || '—'}</span>
                <CopyButton text={referrals.data.code} label="Код" />
              </div>
            </div>
            <div>
              <p className="label">Реферальная ссылка</p>
              <div className="flex items-center justify-between gap-3">
                <span className="truncate text-sm text-ink-700">{referrals.data.link || '—'}</span>
                <CopyButton text={referrals.data.link} label="Ссылку" />
              </div>
            </div>
          </div>
        ) : (
          <EmptyState title="Статистика недоступна" />
        )}
      </section>

      <section>
        <BlockTitle>Запрос выплаты</BlockTitle>
        <form className="card space-y-4 p-5" onSubmit={(event) => void requestPayout(event)}>
          <Field label="Сумма, ₽" hint="Минимум 1000 ₽">
            <input
              className="input"
              type="number"
              min="1000"
              step="0.01"
              inputMode="decimal"
              placeholder="1000"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
          </Field>
          <Field label="Реквизиты" hint="Например, номер карты или счёта">
            <textarea
              className="textarea"
              placeholder="Куда перевести выплату"
              value={requisites}
              onChange={(event) => setRequisites(event.target.value)}
            />
          </Field>
          <button
            type="submit"
            className="btn-primary w-full"
            disabled={payoutBusy || !amount || requisites.trim().length < 3}
          >
            {payoutBusy ? 'Отправляем…' : 'Запросить выплату'}
          </button>
        </form>

        <div className="mt-4">
          <BlockTitle>Мои выплаты</BlockTitle>
          {payouts.loading ? (
            <Spinner label="Загружаем выплаты…" />
          ) : payouts.error ? (
            <ErrorState message={payouts.error} onRetry={payouts.reload} />
          ) : !payouts.data?.length ? (
            <EmptyState title="Выплат пока нет" />
          ) : (
            <div className="space-y-3">
              {payouts.data.map((payout) => (
                <div key={payout.id} className="card-muted p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-ink-900">{money(payout.amount_minor)}</p>
                      <p className="hint mt-1">{date(payout.created_at, true)}</p>
                    </div>
                    <Badge value={payout.status} />
                  </div>
                  <p className="mt-3 break-all text-sm text-ink-600">Реквизиты: {payout.requisites}</p>
                  {payout.admin_note && <p className="hint mt-2">Комментарий: {payout.admin_note}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section>
        <BlockTitle
          action={
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => {
                haptic()
                setTicketOpen(true)
              }}
            >
              Новое обращение
            </button>
          }
        >
          Поддержка
        </BlockTitle>
        {tickets.loading ? (
          <Spinner label="Загружаем обращения…" />
        ) : tickets.error ? (
          <ErrorState message={tickets.error} onRetry={tickets.reload} />
        ) : !tickets.data?.length ? (
          <EmptyState title="Обращений нет" text="Напишите нам, если нужна помощь." />
        ) : (
          <div className="space-y-3">
            {tickets.data.map((ticket) => (
              <button
                key={ticket.id}
                type="button"
                className="card w-full p-4 text-left transition hover:border-gold-300"
                onClick={() => void openTicket(ticket)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-ink-900">{ticket.subject}</p>
                    <p className="hint mt-1">
                      {shortId(ticket.id)} · {date(ticket.updated_at, true)}
                    </p>
                  </div>
                  <Badge value={ticket.status} />
                </div>
                {ticket.messages.length > 0 && (
                  <p className="mt-2 line-clamp-2 text-sm text-ink-600">
                    {ticket.messages[ticket.messages.length - 1].text}
                  </p>
                )}
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <button
          type="button"
          className="btn-ghost w-full"
          onClick={() => {
            haptic()
            setLogoutOpen(true)
          }}
        >
          Выйти
        </button>
        {config.app_env !== 'prod' && (
          <p className="hint text-center">Локальный демо-режим · {config.app_env}</p>
        )}
      </section>

      <Modal open={ticketOpen} title="Новое обращение" onClose={() => setTicketOpen(false)}>
        <form className="space-y-4" onSubmit={(event) => void createTicket(event)}>
          <Field label="Тема">
            <input
              className="input"
              placeholder="Например, вопрос по подписке"
              value={ticketSubject}
              onChange={(event) => setTicketSubject(event.target.value)}
            />
          </Field>
          <Field label="Сообщение">
            <textarea
              className="textarea"
              placeholder="Опишите ситуацию подробнее"
              value={ticketMessage}
              onChange={(event) => setTicketMessage(event.target.value)}
            />
          </Field>
          <div className="flex gap-2">
            <button
              type="submit"
              className="btn-gold flex-1"
              disabled={ticketBusy || ticketMessage.trim().length < 2}
            >
              {ticketBusy ? 'Отправляем…' : 'Отправить'}
            </button>
            <button type="button" className="btn-ghost flex-1" onClick={() => setTicketOpen(false)}>
              Отмена
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={activeTicket !== null || ticketLoading}
        title="Обращение"
        onClose={() => setActiveTicket(null)}
      >
        {ticketLoading ? (
          <Spinner label="Открываем обращение…" />
        ) : activeTicket ? (
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium text-ink-900">{activeTicket.subject}</p>
                <p className="hint mt-1">{date(activeTicket.created_at, true)}</p>
              </div>
              <Badge value={activeTicket.status} />
            </div>
            <div className="space-y-3 border-t border-ink-100 pt-4">
              {activeTicket.messages.length ? (
                activeTicket.messages.map((message) => (
                  <div key={message.id} className="card-muted p-3">
                    <p className="label">
                      {message.author_type === 'admin' ? 'Ответ поддержки' : 'Вы'} ·{' '}
                      {date(message.created_at, true)}
                    </p>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
                      {message.text}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-ink-500">Сообщений пока нет.</p>
              )}
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal open={logoutOpen} title="Выйти из аккаунта?" onClose={() => setLogoutOpen(false)}>
        <p className="text-sm leading-relaxed text-ink-600">
          Токен доступа будет удалён с этого устройства.
        </p>
        <div className="mt-5 flex gap-2">
          <button
            type="button"
            className="btn-danger flex-1"
            onClick={() => {
              notify('Вы вышли из аккаунта')
              signOut()
            }}
          >
            Выйти
          </button>
          <button type="button" className="btn-ghost flex-1" onClick={() => setLogoutOpen(false)}>
            Отмена
          </button>
        </div>
      </Modal>
    </div>
  )
}
