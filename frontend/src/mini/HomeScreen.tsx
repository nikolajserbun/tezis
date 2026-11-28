import { Badge, EmptyState, ErrorState, PageHeader, Spinner } from '../components/ui'
import { date, neurons } from '../lib/format'
import type { Subscription } from '../lib/api'
import { useMini, useMiniApi } from './context'
import { BlockTitle } from './parts'

function QuickAction({
  title,
  text,
  icon,
  index,
  onClick,
  wide = false,
}: {
  title: string
  text: string
  icon: string
  index: number
  onClick: () => void
  wide?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{ animationDelay: `${index * 70}ms` }}
      className={`card mini-reveal group p-4 text-left ${wide ? 'col-span-2' : ''}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="mini-action-icon" aria-hidden>
          {icon}
        </span>
        <span className="text-gold-600 transition-transform group-hover:translate-x-1" aria-hidden>
          →
        </span>
      </div>
      <span className="mt-3 block font-display text-lg font-semibold text-ink-900">{title}</span>
      <p className="hint mt-1.5">{text}</p>
    </button>
  )
}

export function HomeScreen() {
  const { me, go, ordersVersion } = useMini()
  const { usage, user } = me
  const subscription = useMiniApi<Subscription | null>('/api/v1/me/subscription', [ordersVersion])

  const limit = usage.neurons_limit
  const used = usage.neurons_used
  const left = usage.neurons_left
  const progress = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0
  const firstName = user.first_name?.trim() || 'друг'

  return (
    <div className="space-y-6">
      <PageHeader title={`Здравствуйте, ${firstName}`} subtitle="Ваша студия контента в Telegram." />

      <section className="card mini-hero overflow-hidden p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="label">Ваш доступ</p>
            <p className="font-display text-2xl font-semibold text-ink-900">
              {usage.plan_title || 'Бесплатный доступ'}
            </p>
          </div>
          {usage.has_subscription ? (
            <Badge value="active" />
          ) : (
            <span className="badge-gold whitespace-nowrap">Бесплатно</span>
          )}
        </div>

        <div className="mt-5 flex items-end justify-between gap-3">
          <p className="mini-hero-value font-display text-3xl font-semibold text-ink-900">
            {neurons(left)}
            <span className="ml-2 text-sm font-sans font-normal text-ink-500">Neurons</span>
          </p>
          <p className="hint">
            Использовано {neurons(used)} из {neurons(limit)}
          </p>
        </div>
        <div className="mini-progress mt-3 h-2 overflow-hidden rounded-full bg-ink-100">
          <span style={{ width: `${progress}%` }} />
        </div>
        <p className="hint mt-3">
          {usage.resets_at
            ? `Обновление ${date(usage.resets_at)} · подписка до ${date(usage.expires_at)}`
            : 'Бесплатные Neurons не обновляются — оформите подписку для еженедельного пополнения'}
        </p>
      </section>

      <section>
        <BlockTitle>Быстрый старт</BlockTitle>
        <div className="grid grid-cols-2 gap-3">
          <QuickAction
            title="Студия"
            text="Создать пост, план или сценарий"
            icon="✦"
            index={0}
            onClick={() => go('studio')}
          />
          <QuickAction
            title="Магазин"
            text="Подписки и цифровые продукты"
            icon="◈"
            index={1}
            onClick={() => go('shop')}
          />
          <QuickAction
            title="Партнёрская программа"
            text="25 ₽ за друга после первого запроса"
            icon="↗"
            index={2}
            onClick={() => go('profile', 'referrals')}
            wide
          />
        </div>
      </section>

      <section>
        <BlockTitle
          action={
            subscription.data === null ? (
              <button type="button" className="btn-ghost btn-sm" onClick={() => go('shop')}>
                В магазин
              </button>
            ) : undefined
          }
        >
          Активная подписка
        </BlockTitle>
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
              <span className="text-ink-500">Neurons на неделю</span>
              <span className="font-medium text-ink-900">
                {neurons(subscription.data.neurons_used)} / {neurons(subscription.data.neurons_limit)}
              </span>
            </div>
            {subscription.data.auto_renew && (
              <p className="hint mt-3">Автопродление включено</p>
            )}
          </div>
        ) : (
          <EmptyState title="Активной подписки нет" text="Выберите тариф в магазине." />
        )}
      </section>

      {!usage.has_subscription && (
        <button type="button" className="btn-gold w-full" onClick={() => go('shop')}>
          Выбрать тариф
        </button>
      )}
    </div>
  )
}
