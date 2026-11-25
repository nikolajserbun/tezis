import { useState, type FormEvent } from 'react'
import { useApi, type SupportTicket } from '../lib/api'
import { Modal, PageHeader } from '../components/ui'
import { date, shortId } from '../lib/format'
import { DataState, FilterTabs, StatusPill, ToastHost, useAdminActions } from './shared'

type TicketFilter = 'all' | 'open' | 'answered' | 'closed'

const FILTERS: { value: TicketFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'open', label: 'Открытые' },
  { value: 'answered', label: 'Отвеченные' },
  { value: 'closed', label: 'Закрытые' },
]

export default function SupportSection() {
  const [filter, setFilter] = useState<TicketFilter>('all')
  const [selected, setSelected] = useState<SupportTicket | null>(null)
  const [reply, setReply] = useState('')
  const [confirmClose, setConfirmClose] = useState(false)
  const { toast, notify, hideToast, busy, run } = useAdminActions()
  const path = `/api/v1/admin/support/tickets${filter === 'all' ? '' : `?status=${filter}`}`
  const { data, error, loading, reload } = useApi<SupportTicket[]>(path)

  function openTicket(ticket: SupportTicket) {
    setSelected(ticket)
    setReply('')
    setConfirmClose(false)
  }

  async function handleReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected || !reply.trim()) return
    const result = await run<SupportTicket>(`/api/v1/admin/support/tickets/${selected.id}/reply`, {
      method: 'POST',
      body: { text: reply.trim() },
    })
    if (result) {
      setSelected(result)
      setReply('')
      notify('Ответ отправлен')
      reload()
    }
  }

  async function handleClose() {
    if (!selected) return
    const result = await run<SupportTicket>(`/api/v1/admin/support/tickets/${selected.id}/close`, {
      method: 'POST',
    })
    if (result) {
      setSelected(result)
      setConfirmClose(false)
      notify('Тикет закрыт')
      reload()
    }
  }

  return (
    <>
      <PageHeader title="Поддержка" subtitle="Обращения пользователей и ответы." />
      <FilterTabs value={filter} options={FILTERS} onChange={setFilter} />

      <section className="card p-5">
        <DataState loading={loading} error={error} onRetry={reload} empty={!data?.length}>
          {data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Тема</th>
                    <th>Пользователь</th>
                    <th>Приоритет</th>
                    <th>Статус</th>
                    <th>Обновлён</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((ticket) => (
                    <tr key={ticket.id}>
                      <td>
                        <p className="font-medium">{ticket.subject}</p>
                        <p className="hint">{ticket.messages.length} сообщений</p>
                      </td>
                      <td className="font-mono text-xs">{shortId(ticket.user_id)}</td>
                      <td>{ticket.priority}</td>
                      <td><StatusPill value={ticket.status} /></td>
                      <td className="whitespace-nowrap text-xs text-ink-500">{date(ticket.updated_at, true)}</td>
                      <td>
                        <button type="button" className="btn-ghost btn-sm" onClick={() => openTicket(ticket)}>
                          Открыть
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </section>

      <Modal open={Boolean(selected)} title={selected?.subject ?? 'Тикет'} onClose={() => setSelected(null)}>
        {selected && (
          <div className="space-y-5">
            <div className="card-muted flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
              <span>Тикет <span className="font-mono">{shortId(selected.id)}</span></span>
              <span className="flex items-center gap-2">
                <StatusPill value={selected.status} />
                <span className="hint">{date(selected.created_at, true)}</span>
              </span>
            </div>

            <div className="max-h-[320px] space-y-3 overflow-y-auto pr-1">
              {selected.messages.map((message) => (
                <div key={message.id} className="rounded-xl border border-ink-100 p-3">
                  <div className="mb-1.5 flex items-center justify-between gap-2 text-xs text-ink-500">
                    <span>{message.author_type === 'user' ? 'Пользователь' : 'Поддержка'}</span>
                    <span>{date(message.created_at, true)}</span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-ink-800">{message.text}</p>
                </div>
              ))}
            </div>

            {selected.status !== 'closed' && (
              <form onSubmit={handleReply} className="space-y-3 border-t border-ink-100 pt-4">
                <textarea
                  className="textarea min-h-[90px]"
                  value={reply}
                  onChange={(event) => setReply(event.target.value)}
                  placeholder="Ваш ответ пользователю"
                  required
                />
                <button type="submit" className="btn-primary w-full" disabled={busy || !reply.trim()}>
                  {busy ? 'Отправляем…' : 'Ответить'}
                </button>
              </form>
            )}

            {selected.status !== 'closed' && (
              <div className="border-t border-ink-100 pt-4">
                {confirmClose ? (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-ink-50 p-3">
                    <span className="text-sm text-ink-700">Вы уверены, что хотите закрыть тикет?</span>
                    <div className="flex gap-2">
                      <button type="button" className="btn-ghost btn-sm" onClick={() => setConfirmClose(false)}>
                        Нет
                      </button>
                      <button type="button" className="btn-danger btn-sm" disabled={busy} onClick={() => void handleClose()}>
                        Да, закрыть
                      </button>
                    </div>
                  </div>
                ) : (
                  <button type="button" className="btn-ghost w-full" onClick={() => setConfirmClose(true)}>
                    Закрыть тикет
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </Modal>

      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}
