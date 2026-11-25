import { useApi, type Payment } from '../lib/api'
import { PageHeader } from '../components/ui'
import { date, money, shortId } from '../lib/format'
import { DataState, StatusPill } from './shared'

export default function PaymentsSection() {
  const { data, error, loading, reload } = useApi<Payment[]>('/api/v1/admin/payments')

  return (
    <>
      <PageHeader title="Платежи" subtitle="Все транзакции платёжных провайдеров." />
      <section className="card p-5">
        <DataState loading={loading} error={error} onRetry={reload} empty={!data?.length}>
          {data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Платёж</th>
                    <th>Провайдер</th>
                    <th>ID провайдера</th>
                    <th>Сумма</th>
                    <th>Звёзды</th>
                    <th>Статус</th>
                    <th>Дата</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((payment) => (
                    <tr key={payment.id}>
                      <td className="font-mono text-xs">{shortId(payment.id)}</td>
                      <td>{payment.provider}</td>
                      <td className="max-w-[180px] truncate font-mono text-xs" title={payment.provider_payment_id}>
                        {payment.provider_payment_id}
                      </td>
                      <td className="whitespace-nowrap">{money(payment.amount_minor, payment.currency)}</td>
                      <td>{payment.amount_stars || '—'}</td>
                      <td><StatusPill value={payment.status} /></td>
                      <td className="whitespace-nowrap text-xs text-ink-500">{date(payment.created_at, true)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </section>
    </>
  )
}
