import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { EmptyState, ErrorState, Field, Modal, PageHeader, Spinner } from '../components/ui'
import { copyToClipboard, date, plainText } from '../lib/format'
import type { BrandProfile, Generation } from '../lib/api'
import { useMini, useMiniApi } from './context'
import { BlockTitle } from './parts'

type GenerationKind = 'post' | 'plan' | 'reels' | 'story' | 'adapt' | 'objections'
type Platform = 'telegram' | 'instagram' | 'vk' | 'email'

const KINDS: { value: GenerationKind; label: string }[] = [
  { value: 'post', label: 'Пост' },
  { value: 'plan', label: 'Контент-план' },
  { value: 'reels', label: 'Сценарий Reels' },
  { value: 'story', label: 'Рассказ' },
  { value: 'adapt', label: 'Адаптация текста' },
  { value: 'objections', label: 'Работа с возражениями' },
]

const PLATFORMS: { value: Platform; label: string }[] = [
  { value: 'telegram', label: 'Telegram' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'vk', label: 'ВКонтакте' },
  { value: 'email', label: 'Email' },
]

const EMPTY_BRAND: BrandProfile = { niche: '', audience: '', tone: '', goals: '', taboos: '' }

function labelFor<T extends string>(items: { value: T; label: string }[], value: string): string {
  return items.find((item) => item.value === value)?.label ?? value
}

export function StudioScreen() {
  const { me, run, refreshMe, notify, haptic } = useMini()
  const [brand, setBrand] = useState<BrandProfile>(EMPTY_BRAND)
  const [savingBrand, setSavingBrand] = useState(false)
  const [kind, setKind] = useState<GenerationKind>('post')
  const [platform, setPlatform] = useState<Platform>('telegram')
  const [topic, setTopic] = useState('')
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<Generation | null>(null)
  const [savedOnly, setSavedOnly] = useState(false)
  const [busyResult, setBusyResult] = useState(false)
  const [adaptOpen, setAdaptOpen] = useState(false)
  const [adaptPlatform, setAdaptPlatform] = useState<Platform>('instagram')
  const resultRef = useRef<HTMLDivElement | null>(null)
  const history = useMiniApi<Generation[]>(`/api/v1/me/generations?saved_only=${savedOnly}`, [
    savedOnly,
  ])

  useEffect(() => {
    if (me.brand) setBrand({ ...me.brand })
  }, [me.brand])

  const showResult = (generation: Generation): void => {
    setResult(generation)
    window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 30)
  }

  const updateBrandField = (field: keyof BrandProfile, value: string): void => {
    setBrand((current) => ({ ...current, [field]: value }))
  }

  const saveBrand = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    setSavingBrand(true)
    const updated = await run<BrandProfile>('/api/v1/me/brand', { method: 'PATCH', body: brand })
    setSavingBrand(false)
    if (!updated) return
    setBrand({ ...updated })
    notify('Профиль бренда сохранён')
    refreshMe()
  }

  const generate = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    const cleanTopic = topic.trim()
    if (!cleanTopic) {
      notify('Введите тему генерации')
      return
    }
    setGenerating(true)
    const created = await run<Generation>('/api/v1/me/generations', {
      method: 'POST',
      body: { kind, platform, topic: cleanTopic },
    })
    setGenerating(false)
    if (!created) return
    notify('Генерация готова')
    showResult(created)
    history.reload()
    refreshMe()
  }

  const toggleSaved = async (): Promise<void> => {
    if (!result) return
    setBusyResult(true)
    const updated = await run<Generation>(
      `/api/v1/me/generations/${result.id}/save?saved=${!result.is_saved}`,
      { method: 'POST' },
    )
    setBusyResult(false)
    if (!updated) return
    setResult(updated)
    history.reload()
    notify(updated.is_saved ? 'Добавлено в сохранённое' : 'Убрано из сохранённого')
  }

  const shorten = async (): Promise<void> => {
    if (!result) return
    setBusyResult(true)
    const updated = await run<Generation>(`/api/v1/me/generations/${result.id}/shorten`, {
      method: 'POST',
    })
    setBusyResult(false)
    if (!updated) return
    setResult(updated)
    history.reload()
    refreshMe()
    notify('Текст сокращён')
  }

  const adapt = async (): Promise<void> => {
    if (!result) return
    setBusyResult(true)
    const updated = await run<Generation>(`/api/v1/me/generations/${result.id}/adapt`, {
      method: 'POST',
      body: { platform: adaptPlatform },
    })
    setBusyResult(false)
    if (!updated) return
    setResult(updated)
    setAdaptOpen(false)
    history.reload()
    refreshMe()
    notify(`Адаптировано под ${labelFor(PLATFORMS, adaptPlatform)}`)
  }

  const copyResult = (): void => {
    if (!result) return
    haptic()
    void copyToClipboard(plainText(result.result)).then((ok) => notify(ok ? 'Текст скопирован' : 'Не удалось скопировать'))
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Студия" subtitle="Настройте голос бренда и создавайте тексты." />

      <section>
        <BlockTitle>Профиль бренда</BlockTitle>
        <form className="card space-y-4 p-5" onSubmit={(event) => void saveBrand(event)}>
          <Field label="Ниша">
            <input
              className="input"
              placeholder="Например, психология и саморазвитие"
              value={brand.niche}
              onChange={(event) => updateBrandField('niche', event.target.value)}
            />
          </Field>
          <Field label="Аудитория">
            <textarea
              className="textarea"
              placeholder="Кто ваши клиенты и что их волнует"
              value={brand.audience}
              onChange={(event) => updateBrandField('audience', event.target.value)}
            />
          </Field>
          <Field label="Тон голоса">
            <input
              className="input"
              placeholder="Спокойный, экспертный, дружелюбный"
              value={brand.tone}
              onChange={(event) => updateBrandField('tone', event.target.value)}
            />
          </Field>
          <Field label="Цели">
            <textarea
              className="textarea"
              placeholder="Каких результатов хотите добиться"
              value={brand.goals}
              onChange={(event) => updateBrandField('goals', event.target.value)}
            />
          </Field>
          <Field label="Табу" hint="Чего избегать в текстах">
            <textarea
              className="textarea"
              placeholder="Например, агрессивные продажи и обещания"
              value={brand.taboos}
              onChange={(event) => updateBrandField('taboos', event.target.value)}
            />
          </Field>
          <button type="submit" className="btn-primary w-full" disabled={savingBrand}>
            {savingBrand ? 'Сохраняем…' : 'Сохранить профиль'}
          </button>
        </form>
      </section>

      <section>
        <BlockTitle>Новая генерация</BlockTitle>
        <form className="card space-y-4 p-5" onSubmit={(event) => void generate(event)}>
          <Field label="Тип текста">
            <select
              className="select"
              value={kind}
              onChange={(event) => setKind(event.target.value as GenerationKind)}
            >
              {KINDS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Площадка">
            <select
              className="select"
              value={platform}
              onChange={(event) => setPlatform(event.target.value as Platform)}
            >
              {PLATFORMS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Тема" hint="Опишите идею или задачу своими словами">
            <textarea
              className="textarea"
              placeholder="Например, как выбрать эксперта по позиционированию"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
            />
          </Field>
          <div className="flex items-center justify-between gap-3">
            <p className="hint">
              Осталось: {me.usage.generations_left}{' '}
              {me.usage.generations_left === 1 ? 'генерация' : 'генераций'}
            </p>
            <button type="submit" className="btn-gold" disabled={generating || !topic.trim()}>
              {generating ? 'Генерируем…' : 'Создать'}
            </button>
          </div>
        </form>
      </section>

      {result && (
        <section ref={resultRef}>
          <BlockTitle>Результат</BlockTitle>
          <div className="card p-5">
            <div className="flex items-start justify-between gap-3">
              <span className="badge-neutral">
                {labelFor(KINDS, result.kind)} · {labelFor(PLATFORMS, result.platform)}
              </span>
              {result.is_saved && <span className="badge-gold">Сохранено</span>}
            </div>
            <p className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
              {plainText(result.result)}
            </p>
            <div className="mt-4 flex items-center justify-end gap-3 border-t border-ink-100 pt-4">
              <span className="hint">{date(result.created_at, true)}</span>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-ghost btn-sm"
                disabled={busyResult}
                onClick={() => void toggleSaved()}
              >
                {result.is_saved ? 'Убрать из сохранённого' : 'Сохранить'}
              </button>
              <button
                type="button"
                className="btn-ghost btn-sm"
                disabled={busyResult}
                onClick={() => {
                  haptic()
                  setAdaptPlatform(result.platform === 'telegram' ? 'instagram' : 'telegram')
                  setAdaptOpen(true)
                }}
              >
                Адаптировать
              </button>
              <button
                type="button"
                className="btn-ghost btn-sm"
                disabled={busyResult}
                onClick={() => void shorten()}
              >
                Сократить
              </button>
              <button type="button" className="btn-ghost btn-sm" onClick={copyResult}>
                Скопировать
              </button>
            </div>
          </div>
        </section>
      )}

      <section>
        <BlockTitle
          action={
            <button
              type="button"
              className={savedOnly ? 'btn-primary btn-sm' : 'btn-ghost btn-sm'}
              onClick={() => {
                haptic()
                setSavedOnly((value) => !value)
              }}
            >
              Только сохранённые {savedOnly ? '✓' : ''}
            </button>
          }
        >
          История генераций
        </BlockTitle>
        {history.loading ? (
          <Spinner label="Загружаем историю…" />
        ) : history.error ? (
          <ErrorState message={history.error} onRetry={history.reload} />
        ) : !history.data?.length ? (
          <EmptyState
            title="Пока нет генераций"
            text={savedOnly ? 'Сохраните текст, чтобы он появился здесь.' : 'Создайте первый текст выше.'}
          />
        ) : (
          <div className="space-y-3">
            {history.data.map((item) => (
              <button
                key={item.id}
                type="button"
                className="card w-full p-4 text-left transition hover:border-gold-300"
                onClick={() => {
                  haptic()
                  showResult(item)
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm font-medium text-ink-900">
                    {labelFor(KINDS, item.kind)} · {labelFor(PLATFORMS, item.platform)}
                  </span>
                  <span className="hint whitespace-nowrap">{date(item.created_at, true)}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-ink-600">{item.topic || 'Без темы'}</p>
                <div className="mt-2 flex items-center gap-3">
                  {item.is_saved && <span className="badge-gold">Сохранено</span>}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      <Modal open={adaptOpen} title="Адаптировать текст" onClose={() => setAdaptOpen(false)}>
        <Field label="Новая площадка">
          <select
            className="select"
            value={adaptPlatform}
            onChange={(event) => setAdaptPlatform(event.target.value as Platform)}
          >
            {PLATFORMS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </Field>
        <div className="mt-5 flex gap-2">
          <button
            type="button"
            className="btn-gold flex-1"
            disabled={busyResult}
            onClick={() => void adapt()}
          >
            {busyResult ? 'Адаптируем…' : 'Адаптировать'}
          </button>
          <button type="button" className="btn-ghost flex-1" onClick={() => setAdaptOpen(false)}>
            Отмена
          </button>
        </div>
      </Modal>
    </div>
  )
}
