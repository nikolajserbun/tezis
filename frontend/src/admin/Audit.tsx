import { useState } from 'react'
import { useApi, type AuditLog } from '../lib/api'
import { PageHeader } from '../components/ui'
import { date, shortId } from '../lib/format'
import { DataState } from './shared'

const LIMITS = [50, 100, 200]

export default function AuditSection() {
  const [limit, setLimit] = useState(200)
  const { data, error, loading, reload } = useApi<AuditLog[]>(`/api/v1/admin/audit?limit=${limit}`)

  return (
    <>
      <PageHeader
        title="Журнал действий"
        subtitle="Кто и что изменил в панели управления."
        action={
          <select
            className="select w-auto"
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
            aria-label="Количество записей"
          >
            {LIMITS.map((value) => (
              <option key={value} value={value}>{value} записей</option>
            ))}
          </select>
        }
      />

      <section className="card p-5">
        <DataState loading={loading} error={error} onRetry={reload} empty={!data?.length}>
          {data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Сотрудник</th>
                    <th>Действие</th>
                    <th>Объект</th>
                    <th>Данные</th>
                    <th>IP</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((log) => (
                    <tr key={log.id}>
                      <td className="whitespace-nowrap text-xs text-ink-500">{date(log.created_at, true)}</td>
                      <td className="font-mono text-xs">{shortId(log.actor_id)}</td>
                      <td className="font-medium">{log.action}</td>
                      <td>
                        <span>{log.entity_type}</span>
                        {log.entity_id && <span className="hint block font-mono">{shortId(log.entity_id)}</span>}
                      </td>
                      <td className="max-w-[280px]">
                        <code className="block truncate text-xs text-ink-600" title={JSON.stringify(log.payload)}>
                          {JSON.stringify(log.payload)}
                        </code>
                      </td>
                      <td className="whitespace-nowrap text-xs text-ink-500">{log.ip ?? '—'}</td>
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
