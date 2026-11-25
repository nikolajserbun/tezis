import { useState, type FormEvent } from 'react'
import { useApi, type Expense } from '../lib/api'
import { Field, Modal, PageHeader } from '../components/ui'
import { date, money } from '../lib/format'
import { DataState, ToastHost, useAdminActions } from './shared'

interface ExpenseForm {
  category: string
  amount: string
  currency: string
  spentAt: string
  note: string
}

function emptyForm(): ExpenseForm {
  return {
    category: '',
    amount: '',
    currency: 'RUB',
    spentAt: new Date().toISOString().slice(0, 10),
    note: '',
  }
}

export default function ExpensesSection() {
  const { data, error, loading, reload } = useApi<Expense[]>('/api/v1/admin/expenses?limit=100')
  const { toast, notify, hideToast, busy, run } = useAdminActions()
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<ExpenseForm>(emptyForm)

  function closeModal() {
    setModalOpen(false)
    setForm(emptyForm())
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const amountMinor = Math.round(Number(form.amount) * 100)
    if (!Number.isFinite(amountMinor) || amountMinor <= 0) {
      notify('Сумма расхода должна быть больше нуля')
      return
    }
    const result = await run<Expense>('/api/v1/admin/expenses', {
      method: 'POST',
      body: {
        category: form.category.trim(),
        amount_minor: amountMinor,
        currency: form.currency.trim() || 'RUB',
        spent_at: form.spentAt,
        note: form.note.trim(),
      },
    })
    if (result) {
      notify('Расход добавлен')
      closeModal()
      reload()
    }
  }

  return (
    <>
      <PageHeader
        title="Расходы"
        subtitle="Затраты, участвующие в расчёте прибыли."
        action={
          <button type="button" className="btn-primary" onClick={() => setModalOpen(true)}>
            Добавить расход
          </button>
        }
      />

      <section className="card p-5">
        <DataState loading={loading} error={error} onRetry={reload} empty={!data?.length}>
          {data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Категория</th>
                    <th>Сумма</th>
                    <th>Дата</th>
                    <th>Заметка</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((expense) => (
                    <tr key={expense.id}>
                      <td className="font-medium">{expense.category}</td>
                      <td className="whitespace-nowrap text-red-700">
                        −{money(expense.amount_minor, expense.currency)}
                      </td>
                      <td className="whitespace-nowrap">{date(expense.spent_at)}</td>
                      <td className="max-w-[320px] text-ink-500">{expense.note || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DataState>
      </section>

      <Modal open={modalOpen} title="Новый расход" onClose={closeModal}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Категория">
              <input
                className="input"
                value={form.category}
                onChange={(event) => setForm({ ...form, category: event.target.value })}
                minLength={2}
                maxLength={64}
                required
              />
            </Field>
            <Field label="Сумма, ₽">
              <input
                className="input"
                type="number"
                min="0.01"
                step="0.01"
                value={form.amount}
                onChange={(event) => setForm({ ...form, amount: event.target.value })}
                required
              />
            </Field>
            <Field label="Валюта">
              <input
                className="input"
                value={form.currency}
                onChange={(event) => setForm({ ...form, currency: event.target.value })}
              />
            </Field>
            <Field label="Дата расхода">
              <input
                className="input"
                type="date"
                value={form.spentAt}
                onChange={(event) => setForm({ ...form, spentAt: event.target.value })}
                required
              />
            </Field>
          </div>
          <Field label="Заметка">
            <textarea
              className="textarea min-h-[80px]"
              value={form.note}
              onChange={(event) => setForm({ ...form, note: event.target.value })}
              maxLength={500}
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-ghost" onClick={closeModal}>Отмена</button>
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? 'Добавляем…' : 'Добавить'}
            </button>
          </div>
        </form>
      </Modal>

      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}
