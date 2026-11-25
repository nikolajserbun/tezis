import { Link, Navigate, Route, Routes } from 'react-router-dom'
import AdminApp from './admin/AdminApp'
import MiniApp from './mini/MiniApp'

function Landing() {
  const telegram = import.meta.env.VITE_BOT_USERNAME
  return (
    <main className="min-h-screen bg-ivory">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-6">
        <span className="font-display text-xl font-semibold tracking-tight">Тезис</span>
        <nav className="flex items-center gap-2 text-sm">
          <Link className="btn-ghost btn-sm" to="/app">Mini App</Link>
          <Link className="btn-primary btn-sm" to="/admin">Админка</Link>
        </nav>
      </header>

      <section className="mx-auto max-w-6xl px-5 pb-16 pt-12 sm:pt-20">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-gold-600">
          AI-контент-студия для экспертов
        </p>
        <h1 className="max-w-3xl font-display text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
          Ваши идеи — в тексты, которые читают и сохраняют.
        </h1>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-ink-600 sm:text-lg">
          Тезис помогает экспертам регулярно публиковать сильный контент: посты, сценарии Reels,
          контент-планы и адаптацию под площадки. Внутри Telegram и без лишних инструментов.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link className="btn-primary" to="/app">Открыть студию</Link>
          {telegram && (
            <a className="btn-ghost" href={`https://t.me/${telegram}`} target="_blank" rel="noreferrer">
              Написать боту
            </a>
          )}
          <Link className="btn-ghost" to="/admin">Панель управления</Link>
        </div>

        <div className="mt-14 grid gap-4 sm:grid-cols-3">
          {[
            ['01', 'Профиль бренда', 'Ниша, аудитория, тон и табу — один раз, и генерации учитывают контекст.'],
            ['02', 'Генерации', 'Посты, планы, сценарии и работа с возражениями в лимитах вашего тарифа.'],
            ['03', 'Клуб и магазин', 'Цифровые продукты, закрытое сообщество и партнёрская программа.'],
          ].map(([num, title, text]) => (
            <div key={num} className="card p-6">
              <p className="font-display text-sm text-gold-600">{num}</p>
              <h2 className="mt-3 font-display text-xl font-semibold">{title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-ink-600">{text}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app/*" element={<MiniApp />} />
      <Route path="/admin/*" element={<AdminApp />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
