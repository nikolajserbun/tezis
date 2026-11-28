import { useState, type FormEvent } from 'react'
import { useApi, type Product } from '../lib/api'
import { Field, Modal, PageHeader } from '../components/ui'
import { money } from '../lib/format'
import { DataState, RowActions, ToastHost, useAdminActions } from './shared'

interface ProductFormState {
  slug: string
  title: string
  description: string
  kind: 'digital' | 'subscription'
  price: string
  currency: string
  priceStars: string
  durationDays: string
  neuronsPerWeek: string
  brandLimit: string
  fileKey: string
  coverUrl: string
  features: string
  isActive: boolean
  sortOrder: string
}

function emptyForm(): ProductFormState {
  return {
    slug: '',
    title: '',
    description: '',
    kind: 'digital',
    price: '0',
    currency: 'RUB',
    priceStars: '',
    durationDays: '',
    neuronsPerWeek: '',
    brandLimit: '1',
    fileKey: '',
    coverUrl: '',
    features: '',
    isActive: true,
    sortOrder: '0',
  }
}

function formFromProduct(product: Product): ProductFormState {
  return {
    slug: product.slug,
    title: product.title,
    description: product.description,
    kind: product.kind === 'subscription' ? 'subscription' : 'digital',
    price: String(product.price_minor / 100),
    currency: product.currency,
    priceStars: product.price_stars === null ? '' : String(product.price_stars),
    durationDays: product.duration_days === null ? '' : String(product.duration_days),
    neuronsPerWeek: product.kind === 'subscription' ? String(product.neurons_per_week) : '',
    brandLimit: String(product.brand_limit),
    fileKey: product.file_key ?? '',
    coverUrl: product.cover_url ?? '',
    features: product.features.join('\n'),
    isActive: product.is_active,
    sortOrder: String(product.sort_order),
  }
}

function optionalInt(value: string, label: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = Number(trimmed)
  if (!Number.isInteger(parsed) || parsed < 0) throw new Error(`${label}: введите целое число`)
  return parsed
}

function optionalFloat(value: string, label: string): number {
  const trimmed = value.trim()
  if (!trimmed) return 0
  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed) || parsed < 0) throw new Error(`${label}: введите число`)
  return parsed
}

export default function ProductsSection({ canManage }: { canManage: boolean }) {
  const { data, error, loading, reload } = useApi<Product[]>('/api/v1/admin/products')
  const { toast, notify, hideToast, busy, run } = useAdminActions()
  const [editing, setEditing] = useState<Product | null>(null)
  const [form, setForm] = useState<ProductFormState>(emptyForm)
  const [modalOpen, setModalOpen] = useState(false)
  const [archiving, setArchiving] = useState<Product | null>(null)

  function closeModal() {
    setModalOpen(false)
    setEditing(null)
  }

  function openCreate() {
    setEditing(null)
    setForm(emptyForm())
    setModalOpen(true)
  }

  function openEdit(product: Product) {
    setEditing(product)
    setForm(formFromProduct(product))
    setModalOpen(true)
  }

  function update<K extends keyof ProductFormState>(key: K, value: ProductFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    try {
      const priceMinor = Math.round(Number(form.price) * 100)
      if (!Number.isFinite(priceMinor) || priceMinor < 0) throw new Error('Цена должна быть неотрицательным числом')
      const brandLimit = optionalInt(form.brandLimit, 'Лимит брендов')
      if (brandLimit === null || brandLimit < 1) throw new Error('Лимит брендов должен быть не меньше 1')
      const neuronsPerWeek = optionalFloat(form.neuronsPerWeek, 'Neurons в неделю')
      if (form.kind === 'subscription' && neuronsPerWeek <= 0) {
        throw new Error('Для подписки укажите Neurons в неделю больше нуля')
      }

      const body: Record<string, unknown> = {
        title: form.title.trim(),
        description: form.description,
        price_minor: priceMinor,
        currency: form.currency.trim() || 'RUB',
        price_stars: optionalInt(form.priceStars, 'Цена в звёздах'),
        duration_days: optionalInt(form.durationDays, 'Длительность'),
        neurons_per_week: form.kind === 'subscription' ? neuronsPerWeek : 0,
        brand_limit: brandLimit,
        file_key: form.fileKey.trim() || null,
        cover_url: form.coverUrl.trim() || null,
        features: form.features.split('\n').map((line) => line.trim()).filter(Boolean),
        is_active: form.isActive,
        sort_order: optionalInt(form.sortOrder, 'Порядок') ?? 0,
      }
      if (!editing) {
        body.slug = form.slug.trim()
        body.kind = form.kind
      }

      const result = await run<Product>(
        editing ? `/api/v1/admin/products/${editing.id}` : '/api/v1/admin/products',
        { method: editing ? 'PATCH' : 'POST', body },
      )
      if (result) {
        notify(editing ? 'Товар обновлён' : 'Товар создан')
        closeModal()
        reload()
      }
    } catch (validationError) {
      notify(validationError instanceof Error ? validationError.message : 'Проверьте поля формы')
    }
  }

  async function handleArchive() {
    if (!archiving) return
    const result = await run<{ ok: boolean }>(`/api/v1/admin/products/${archiving.id}`, { method: 'DELETE' })
    if (result) {
      notify('Товар отправлен в архив')
      setArchiving(null)
      reload()
    }
  }

  return (
    <>
      <PageHeader
        title="Товары"
        subtitle="Каталог цифровых продуктов и подписок."
        action={
          canManage ? (
            <button type="button" className="btn-primary" onClick={openCreate}>Новый товар</button>
          ) : undefined
        }
      />

      <section className="card p-5">
        <DataState loading={loading} error={error} onRetry={reload} empty={!data?.length}>
          {data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Товар</th>
                    <th>Тип</th>
                    <th>Цена</th>
                    <th>Лимиты</th>
                    <th>Статус</th>
                    <th>Порядок</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((product) => (
                    <tr key={product.id}>
                      <td>
                        <p className="font-medium">{product.title}</p>
                        <p className="hint font-mono">{product.slug}</p>
                      </td>
                      <td>{product.kind === 'subscription' ? 'Подписка' : 'Цифровой'}</td>
                      <td className="whitespace-nowrap">
                        {money(product.price_minor, product.currency)}
                        {product.price_stars !== null && (
                          <span className="hint block">{product.price_stars} ★</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap text-xs text-ink-500">
                        {product.kind === 'subscription'
                          ? `${product.neurons_per_week} Neurons/нед`
                          : '—'}
                        <span className="block">{product.brand_limit} бренд(а)</span>
                      </td>
                      <td>
                        <span className={product.is_active ? 'badge badge-green' : 'badge badge-neutral'}>
                          {product.is_active ? 'Активен' : 'В архиве'}
                        </span>
                      </td>
                      <td>{product.sort_order}</td>
                      <td>
                        {canManage && product.is_active ? (
                          <RowActions>
                            <button type="button" className="btn-ghost btn-sm" onClick={() => openEdit(product)}>
                              Изменить
                            </button>
                            <button type="button" className="btn-danger btn-sm" onClick={() => setArchiving(product)}>
                              В архив
                            </button>
                          </RowActions>
                        ) : (
                          <span className="hint">{product.is_active ? 'Недостаточно прав' : 'В архиве'}</span>
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

      <Modal
        open={modalOpen}
        title={editing ? 'Редактирование товара' : 'Новый товар'}
        onClose={closeModal}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Slug" hint={editing ? 'Slug нельзя изменить после создания.' : 'Латиницей, например brand-voice-guide.'}>
              <input
                className="input"
                value={form.slug}
                onChange={(event) => update('slug', event.target.value)}
                disabled={Boolean(editing)}
                required={!editing}
              />
            </Field>
            <Field label="Название">
              <input
                className="input"
                value={form.title}
                onChange={(event) => update('title', event.target.value)}
                required
              />
            </Field>
          </div>

          <Field label="Описание">
            <textarea
              className="textarea min-h-[80px]"
              value={form.description}
              onChange={(event) => update('description', event.target.value)}
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Тип" hint={editing ? 'Тип товара фиксирован.' : undefined}>
              <select
                className="select"
                value={form.kind}
                onChange={(event) => update('kind', event.target.value as ProductFormState['kind'])}
                disabled={Boolean(editing)}
              >
                <option value="digital">Цифровой товар</option>
                <option value="subscription">Подписка</option>
              </select>
            </Field>
            <Field label="Валюта">
              <input className="input" value={form.currency} onChange={(event) => update('currency', event.target.value)} />
            </Field>
            <Field label="Цена, ₽">
              <input
                className="input"
                type="number"
                min={0}
                step="0.01"
                value={form.price}
                onChange={(event) => update('price', event.target.value)}
                required
              />
            </Field>
            <Field label="Цена в звёздах" hint="Пусто — рассчитать автоматически.">
              <input
                className="input"
                type="number"
                min={0}
                value={form.priceStars}
                onChange={(event) => update('priceStars', event.target.value)}
              />
            </Field>
            <Field label="Длительность, дней">
              <input
                className="input"
                type="number"
                min={1}
                value={form.durationDays}
                onChange={(event) => update('durationDays', event.target.value)}
              />
            </Field>
            <Field
              label="Neurons в неделю"
              hint={form.kind === 'subscription' ? 'Пополняется каждые 7 дней.' : 'Только для подписок.'}
            >
              <input
                className="input"
                type="number"
                min={0}
                step="0.1"
                value={form.neuronsPerWeek}
                onChange={(event) => update('neuronsPerWeek', event.target.value)}
                disabled={form.kind !== 'subscription'}
              />
            </Field>
            <Field label="Лимит брендов">
              <input
                className="input"
                type="number"
                min={1}
                value={form.brandLimit}
                onChange={(event) => update('brandLimit', event.target.value)}
                required
              />
            </Field>
            <Field label="Порядок сортировки">
              <input
                className="input"
                type="number"
                value={form.sortOrder}
                onChange={(event) => update('sortOrder', event.target.value)}
              />
            </Field>
          </div>

          <Field label="Ключ файла">
            <input className="input" value={form.fileKey} onChange={(event) => update('fileKey', event.target.value)} />
          </Field>
          <Field label="URL обложки">
            <input className="input" value={form.coverUrl} onChange={(event) => update('coverUrl', event.target.value)} />
          </Field>
          <Field label="Возможности" hint="Одна capability на строку.">
            <textarea
              className="textarea min-h-[90px]"
              value={form.features}
              onChange={(event) => update('features', event.target.value)}
              placeholder={'Первая возможность\nВторая возможность'}
            />
          </Field>

          <label className="flex items-center gap-2 text-sm text-ink-800">
            <input
              type="checkbox"
              className="h-4 w-4 accent-ink-900"
              checked={form.isActive}
              onChange={(event) => update('isActive', event.target.checked)}
            />
            Товар активен
          </label>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-ghost" onClick={closeModal}>Отмена</button>
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? 'Сохраняем…' : 'Сохранить'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal open={Boolean(archiving)} title="Отправить товар в архив?" onClose={() => setArchiving(null)}>
        <p className="text-sm text-ink-600">
          Товар «{archiving?.title}» станет недоступен в каталоге. Действие можно отменить повторным редактированием.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={() => setArchiving(null)}>Отмена</button>
          <button type="button" className="btn-danger" disabled={busy} onClick={() => void handleArchive()}>
            В архив
          </button>
        </div>
      </Modal>

      <ToastHost message={toast} onClose={hideToast} />
    </>
  )
}
