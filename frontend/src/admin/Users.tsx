import { useEffect, useState, type FormEvent } from 'react'
import { useApi, type Order, type Subscription, type User } from '../lib/api'
import { Badge, Field, Modal, PageHeader } from '../components/ui'
import { copyToClipboard, date, money, shortId } from '../lib/format'
import { ROLE_LABELS } from './types'
import { DataState, Pagination, RowActions, ToastHost, useAdminActions } from './shared'

function UserDetails({ user, canManage }: { user: User; canManage: boolean }) {
  const orders = useApi<Order[]>(`/api/v1/admin/users/${user.id}/orders`)
  const subscriptions = useApi<Subscription[]>(`/api/v1/admin/users/${user.id}/subscriptions`)
  const { toast, notify, hideToast, busy, run } = useAdminActions()

  async function revoke(subscription: Subscription) {
    const result = await run<Subscription>(
      `/api/v1/admin/subscriptions/${subscription.id}/cancel`,
      { method: 'POST' },
    )
    if (result) {
      notify('Подписка снята')
      subscriptions.reload()
    }
  }

  return (
    <>
      <div className="mt-5 grid gap-5 border-t border-ink-100 pt-5 sm:grid-cols-2">
        <div>
          <h3 className="label">Заказы</h3>
        <DataState loading={orders.loading} error={orders.error} onRetry={orders.reload} empty={!orders.data?.length}>
          <div className="space-y-2">
            {orders.data?.map((order) => (
              <div key={order.id} className="card-muted flex items-center justify-between gap-2 px-3 py-2 text-sm">
                <span className="font-mono text-xs">{shortId(order.id)}</span>
                <span>{money(order.total_minor, order.currency)}</span>
                <Badge value={order.status} />
              </div>
            ))}
          </div>
        </DataState>
      </div>
      <div>
        <h3 className="label">Подписки</h3>
        <DataState loading={subscriptions.loading} error={subscriptions.error} onRetry={subscriptions.reload} empty={!subscriptions.data?.length}>
          <div className="space-y-2">
            {subscriptions.data?.map((subscription) => (
              <div key={subscription.id} className="card-muted flex items-center justify-between gap-2 px-3 py-2 text-sm">
                <span className="truncate">{subscription.product_title ?? 'Без названия'}</span>
                <span className="whitespace-nowrap text-xs text-ink-500">до {date(subscription.expires_at)}</span>
                <Badge value={subscription.status} />
                {canManage && subscription.status === 'active' && (
                  <button
                    type="button"
                    className="btn-ghost btn-sm whitespace-nowrap"
                    disabled={busy}
                    onClick={() => void revoke(subscription)}
                  >
                    Снять
                  </button>
                )}
              </div>
            ))}
          </div>
        </DataState>
      </div>
      </div>
      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}

export default function UsersSection({ canManage }: { canManage: boolean }) {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<User | null>(null)
  const [isBlocked, setIsBlocked] = useState(false)
  const [delta, setDelta] = useState('')
  const [bonusNeurons, setBonusNeurons] = useState('')
  const [neuronsLimit, setNeuronsLimit] = useState('')
  const { toast, notify, hideToast, busy, run } = useAdminActions()

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    setOffset(0)
  }, [query])

  const limit = 20
  const path = `/api/v1/admin/users?q=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}`
  const { data, error, loading, reload } = useApi<User[]>(path)

  function openEditor(user: User) {
    setEditing(user)
    setIsBlocked(user.is_blocked)
    setDelta('')
    setBonusNeurons(String(user.neurons_bonus ?? 0))
    setNeuronsLimit(user.neurons_limit_override === null ? '' : String(user.neurons_limit_override))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editing) return
    const rawDelta = delta.trim()
    if (rawDelta && !Number.isInteger(Number(rawDelta))) {
      notify('Корректировка баланса должна быть целым числом копеек')
      return
    }
    const body: {
      is_blocked: boolean
      balance_delta_minor?: number
      neurons_bonus: number
      neurons_limit_override: number | null
    } = {
      is_blocked: isBlocked,
      neurons_bonus: Number(bonusNeurons) || 0,
      neurons_limit_override: neuronsLimit.trim() === '' ? null : Number(neuronsLimit),
    }
    if (rawDelta) body.balance_delta_minor = Number(rawDelta)

    const result = await run<User>(`/api/v1/admin/users/${editing.id}`, {
      method: 'PATCH',
      body,
    })
    if (result) {
      notify('Пользователь обновлён')
      setEditing(null)
      reload()
    }
  }

  return (
    <>
      <PageHeader
        title="Пользователи"
        subtitle="Поиск, блокировки, бонусы, лимиты и корректировка баланса."
      />

      <section className="card p-5">
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            className="input sm:max-w-sm"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Имя, username или Telegram ID"
            aria-label="Поиск пользователей"
          />
          {search && (
            <button type="button" className="btn-ghost btn-sm self-start" onClick={() => setSearch('')}>
              Сбросить поиск
            </button>
          )}
        </div>

        <DataState loading={loading} error={error} onRetry={reload} empty={!data?.length}>
          {data && (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Пользователь</th>
                      <th>Роль</th>
                      <th>Баланс</th>
                      <th>Лимиты</th>
                      <th>Статус</th>
                      <th>Регистрация</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((user) => (
                      <tr key={user.id}>
                        <td>
                          <p className="font-medium">
                            {user.first_name}
                            {user.last_name ? ` ${user.last_name}` : ''}
                          </p>
                          <p className="hint">
                            {user.username ? `@${user.username} · ` : ''}TG {user.tg_id}
                          </p>
                        </td>
                        <td><span className="badge badge-neutral">{ROLE_LABELS[user.role] ?? user.role}</span></td>
                        <td className="whitespace-nowrap">{money(user.balance_minor)}</td>
                        <td className="whitespace-nowrap text-xs text-ink-600">
                          <p>Доп. Neurons: {user.neurons_bonus}</p>
                          <p>
                            Лимит:{' '}
                            {user.neurons_limit_override === null
                              ? 'по умолчанию'
                              : user.neurons_limit_override}
                          </p>
                        </td>
                        <td>
                          {user.is_blocked ? (
                            <span className="badge badge-red">Заблокирован</span>
                          ) : (
                            <span className="badge badge-green">Активен</span>
                          )}
                        </td>
                        <td className="whitespace-nowrap text-xs text-ink-500">{date(user.created_at)}</td>
                        <td>
                          <RowActions>
                            {canManage ? (
                              <button type="button" className="btn-ghost btn-sm" onClick={() => openEditor(user)}>
                                Изменить
                              </button>
                            ) : (
                              <span className="hint">Недостаточно прав</span>
                            )}
                            <button
                              type="button"
                              className="btn-ghost btn-sm"
                              onClick={() => {
                                void copyToClipboard(user.referral_code).then((ok) =>
                                  notify(ok ? 'Промокод скопирован' : 'Не удалось скопировать'),
                                )
                              }}
                            >
                              Реф. код
                            </button>
                          </RowActions>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination offset={offset} limit={limit} count={data.length} onOffset={setOffset} />
            </>
          )}
        </DataState>
      </section>

      <Modal open={Boolean(editing)} title="Редактирование пользователя" onClose={() => setEditing(null)}>
        {editing && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="card-muted px-4 py-3 text-sm">
              <p className="font-medium">
                {editing.first_name}
                {editing.last_name ? ` ${editing.last_name}` : ''}
              </p>
              <p className="hint">Telegram ID: {editing.tg_id} · ID: {shortId(editing.id)}</p>
            </div>

            <p className="hint">
              Роль «{ROLE_LABELS[editing.role] ?? editing.role}» определяется Telegram ID из
              OWNER_TG_ID и не назначается вручную.
            </p>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Доп. Neurons (±)" hint="Плюс добавить, минус забрать. Прибавляется к лимиту ниже.">
                <input
                  className="input"
                  type="number"
                  step="any"
                  value={bonusNeurons}
                  onChange={(event) => setBonusNeurons(event.target.value)}
                  placeholder="0"
                />
              </Field>
            </div>

            <Field
              label="Лимит Neurons для пользователя"
              hint="Пусто — общий лимит из FREE_NEURONS (у подписчиков лимита нет). Число ≥ 1 задаёт персональный бюджет."
            >
              <input
                className="input"
                type="number"
                step="any"
                min={1}
                value={neuronsLimit}
                onChange={(event) => setNeuronsLimit(event.target.value)}
                placeholder="По умолчанию"
              />
            </Field>

            <label className="flex items-center gap-2 text-sm text-ink-800">
              <input
                type="checkbox"
                className="h-4 w-4 accent-ink-900"
                checked={isBlocked}
                onChange={(event) => setIsBlocked(event.target.checked)}
              />
              Заблокировать пользователя
            </label>

            <Field label="Корректировка баланса, копейки" hint="Положительное число — начисление, отрицательное — списание.">
              <input
                className="input"
                type="number"
                step={1}
                value={delta}
                onChange={(event) => setDelta(event.target.value)}
                placeholder="Например, 5000 или -5000"
              />
            </Field>

            <UserDetails user={editing} canManage={canManage} />

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>Отмена</button>
              <button type="submit" className="btn-primary" disabled={busy}>
                {busy ? 'Сохраняем…' : 'Сохранить'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}
