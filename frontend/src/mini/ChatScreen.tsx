import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { EmptyState, ErrorState, Spinner } from '../components/ui'
import type { ChatAnswer, ChatMessage } from '../lib/api'
import { neurons, plainText } from '../lib/format'
import { useMini, useMiniApi } from './context'
import { BlockTitle } from './parts'
import { openExternal } from './telegram'

export function ChatScreen() {
  const { me, run, notify, refreshMe } = useMini()
  const history = useMiniApi<ChatMessage[]>('/api/v1/me/chat')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [webSearch, setWebSearch] = useState(true)
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const left = me.usage.neurons_left
  const leftLabel = neurons(left)

  useEffect(() => {
    if (history.data) setMessages(history.data)
  }, [history.data])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, busy])

  const send = async (event: FormEvent): Promise<void> => {
    event.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    setBusy(true)
    setInput('')
    setMessages((current) => [
      ...current,
      {
        id: `local-${Date.now()}`,
        role: 'user',
        content: text,
        sources: [],
        demo_mode: false,
        created_at: new Date().toISOString(),
      },
    ])
    const answer = await run<ChatAnswer>('/api/v1/me/chat', {
      method: 'POST',
      body: { message: text, web_search: webSearch },
    })
    if (answer) {
      setMessages((current) => [
        ...current,
        {
          id: answer.id,
          role: 'assistant',
          content: answer.answer,
          sources: answer.sources,
          demo_mode: answer.demo_mode,
          created_at: answer.created_at,
        },
      ])
      refreshMe()
    }
    setBusy(false)
  }

  const clear = async (): Promise<void> => {
    const result = await run<{ deleted: number }>('/api/v1/me/chat', { method: 'DELETE' })
    if (result) {
      setMessages([])
      notify('История чата очищена')
      refreshMe()
    }
  }

  return (
    <div className="space-y-5">
      <PageHeaderChat leftLabel={leftLabel} />
      <section>
        <BlockTitle>Чат-помощник</BlockTitle>
        <div className="card flex flex-col p-4">
          {history.loading ? (
            <Spinner label="Загружаем переписку…" />
          ) : history.error ? (
            <ErrorState message={history.error} onRetry={history.reload} />
          ) : messages.length === 0 ? (
            <EmptyState
              title="Начните разговор"
              text="Спросите о тарифах, контенте, оплате или запуске — бот ответит и приведёт источники."
            />
          ) : (
            <div className="space-y-4">
              {messages.map((item) => (
                <div
                  key={item.id}
                  className={item.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
                >
                  <div
                    className={`mini-bubble max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      item.role === 'user' ? 'mini-bubble-user' : 'mini-bubble-assistant'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{plainText(item.content)}</p>
                    {item.sources.length > 0 && (
                      <div className="mt-3 space-y-2 border-t border-ink-100 pt-3 text-xs">
                        <p className="font-semibold">Источники</p>
                        {item.sources.map((source, index) => (
                          <div key={`${item.id}-${index}`}>
                            {source.url ? (
                              <button
                                type="button"
                                className="text-left text-gold-700 underline"
                                onClick={() => openExternal(source.url)}
                              >
                                {index + 1}. {source.title}
                              </button>
                            ) : (
                              <p>{index + 1}. {source.title}</p>
                            )}
                            <p className="text-ink-500">{plainText(source.snippet)}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    {item.demo_mode && (
                      <p className="mt-3 text-xs text-ink-500">
                        Демо-режим: источники из встроенной базы знаний
                      </p>
                    )}
                  </div>
                </div>
              ))}
              {busy && (
                <div className="flex justify-start">
                  <div className="mini-bubble mini-bubble-assistant mini-typing" aria-label="Бот думает">
                    <i />
                    <i />
                    <i />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </section>

      <form className="card space-y-3 p-4" onSubmit={(event) => void send(event)}>
        <div className="flex items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm text-ink-800">
            <input
              type="checkbox"
              className="h-4 w-4 accent-ink-900"
              checked={webSearch}
              onChange={(event) => setWebSearch(event.target.checked)}
            />
            Искать в интернете
          </label>
          <button
            type="button"
            className="btn-ghost btn-sm"
            disabled={busy || messages.length === 0}
            onClick={() => void clear()}
          >
            Очистить
          </button>
        </div>
        <textarea
          className="input min-h-24 resize-y"
          placeholder="Задайте вопрос по теме, продукту или поищите свежую информацию…"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          maxLength={2000}
        />
        <div className="flex items-center justify-between gap-3">
          <p className="hint">
            Расход Neurons зависит от модели. Доступно: {leftLabel}
            {me.usage.resets_at ? ' · пополнение каждую неделю' : ' · без подписки не пополняется'}
          </p>
          <button
            type="submit"
            className="btn-gold"
            disabled={busy || !input.trim() || left <= 0}
          >
            {busy ? 'Отправляем…' : 'Спросить'}
          </button>
        </div>
      </form>
    </div>
  )
}

function PageHeaderChat({ leftLabel }: { leftLabel: string }) {
  return (
    <header>
      <h1 className="font-display text-2xl font-semibold text-ink-900">Чат</h1>
      <p className="mt-1 text-sm text-ink-600">
        Поможет разобраться в теме и найти материалы. Доступно: {leftLabel}.
      </p>
    </header>
  )
}
