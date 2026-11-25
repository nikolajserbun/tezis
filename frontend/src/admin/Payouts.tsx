import { useState } from 'react'
import { useApi, type Payout } from '../lib/api'
import { Modal, PageHeader } from '../components/ui'
import { date, money, shortId } from '../lib/format'
import type { ReferralEarning } from './types'
import { DataState, FilterTabs, StatusPill, ToastHost, useAdminActions } from './shared'

type PayoutFilter = 'all' | 'pending' | 'approved' | 'rejected' | 'paid'

const FILTERS: { value: PayoutFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'pending', label: 'Ожидают' },
  { value: 'approved', label: 'Одобренные' },
  { value: 'rejected', label: 'Отклонённые' },
  { value: 'paid', label: 'Выплаченные' },
]

export default function PayoutsSection({ canManage }: { canManage: boolean }) {
  const [filter, setFilter] = useState<PayoutFilter>('all')
  const [deciding, setDeciding] = useState<Payout | null>(null)
  const { toast, notify, hideToast, busy, run } = useAdminActions()
  const path = `/api/v1/admin/payouts${filter === 'all' ? '' : `?status=${filter}`}`
  const payouts = useApi<Payout[]>(path)
  const earnings = useApi<ReferralEarning[]>('/api/v1/admin/referral-earnings')

  async function decide(approve: boolean) {
    if (!deciding) return
    const result = await run<Payout>(`/api/v1/admin/payouts/${deciding.id}/${approve ? 'approve' : 'reject'}`, {
      method: 'POST',
    })
    if (result) {
      notify(approve ? 'Заявка одобрена' : 'Заявка отклонена')
      setDeciding(null)
      payouts.reload()
      earnings.reload()
    }
  }

  return (
    <>
      <PageHeader title="Выплаты" subtitle="Заявки партнёров и начисления по рефералам." />
      <FilterTabs value={filter} options={FILTERS} onChange={setFilter} />

      <section className="card p-5">
        <DataState loading={payouts.loading} error={payouts.error} onRetry={payouts.reload} empty={!payouts.data?.length}>
          {payouts.data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Заявка</th>
                    <th>Пользователь</th>
                    <th>Сумма</th>
                    <th>Способ и реквизиты</th>
                    <th>Статус</th>
                    <th>Дата</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {payouts.data.map((payout) => (
                    <tr key={payout.id}>
                      <td className="font-mono text-xs">{shortId(payout.id)}</td>
                      <td className="font-mono text-xs">{shortId(payout.user_id)}</td>
                      <td className="whitespace-nowrap font-medium">{money(payout.amount_minor)}</td>
                      <td>
                        <p>{payout.method}</p>
                        <p className="hint max-w-[220px] truncate" title={payout.requisites}>{payout.requisites}</p>
                      </td>
                      <td><StatusPill value={payout.status} /></td>
                      <td className="whitespace-nowrap text-xs text-ink-500">{date(payout.created_at)}</td>
                      <td>
                        {canManage && payout.status === 'pending' ? (
                          <button type="button" className="btn-gold btn-sm" onClick={() => setDeciding(payout)}>
                            Решить
                          </button>
                        ) : (
                          <span className="hint">{payout.admin_note ?? '—'}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </section>

      <section className="card mt-6 p-5">
        <h2 className="mb-4 font-display text-lg font-semibold">Реферальные начисления</h2>
        <DataState loading={earnings.loading} error={earnings.error} onRetry={earnings.reload} empty={!earnings.data?.length}>
          {earnings.data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Начисление</th>
                    <th>Пригласивший</th>
                    <th>Сумма</th>
                    <th>Основание</th>
                    <th>Статус</th>
                    <th>Дата</th>
                  </tr>
                </thead>
                <tbody>
                  {earnings.data.map((earning) => (
                    <tr key={earning.id}>
                      <td className="font-mono text-xs">{shortId(earning.id)}</td>
                      <td className="whitespace-nowrap">
                        TG {earning.referrer_tg_id}
                        <span className="hint block">{shortId(earning.referrer_id)}</span>
                      </td>
                      <td className="whitespace-nowrap">{money(earning.amount_minor)}</td>
                      <td>
                        {earning.source === 'first_request'
                          ? 'Первый запрос друга'
                          : `${(earning.rate_bp / 100).toFixed(1)}% (старое)`}
                      </td>
                      <td><StatusPill value={earning.status} /></td>
                      <td className="whitespace-nowrap text-xs text-ink-500">{date(earning.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </section>

      <Modal open={Boolean(deciding)} title="Решение по выплате" onClose={() => setDeciding(null)}>
        <p className="text-sm text-ink-600">
          Заявка <span className="font-mono">{shortId(deciding?.id)}</span> на сумму{' '}
          {money(deciding?.amount_minor ?? 0)}. Реквизиты: {deciding?.requisites}
        </p>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={() => setDeciding(null)}>Отмена</button>
          <button type="button" className="btn-danger" disabled={busy} onClick={() => void decide(false)}>
            Отклонить
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void decide(true)}>
            Одобрить
          </button>
        </div>
        <p className="hint mt-3">Решение применяется сразу после нажатия кнопки.</p>
      </Modal>

      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}
