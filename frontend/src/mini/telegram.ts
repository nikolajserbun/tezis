import type { InvoiceClosed, TelegramWebApp, TelegramWebAppWindow } from './types'

export function getWebApp(): TelegramWebApp | null {
  if (typeof window === 'undefined') return null
  const webApp = (window as TelegramWebAppWindow).Telegram?.WebApp
  return webApp ?? null
}

export function getInitData(): string {
  return getWebApp()?.initData?.trim() ?? ''
}

export function haptic(type: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft' = 'light'): void {
  try {
    getWebApp()?.HapticFeedback?.impactOccurred(type)
  } catch {
    /* HapticFeedback может отсутствовать в старых клиентах */
  }
}

export function initTelegram(): void {
  const webApp = getWebApp()
  if (!webApp) return

  const call = (handler?: () => void): void => {
    try {
      handler?.()
    } catch {
      /* Метод может быть недоступен в конкретной версии клиента */
    }
  }

  call(() => webApp.ready())
  call(() => webApp.expand())
  call(() => webApp.enableClosingConfirmation?.())
  call(() => webApp.setHeaderColor?.('#F5F2EC'))
  call(() => webApp.setBackgroundColor?.('#F5F2EC'))

  const closeButton = webApp.CloseButton
  if (closeButton) {
    const onClose = (): void => haptic()
    call(() => closeButton.onClick(onClose))
    call(() => closeButton.show())
  }
}

export function bindBackButton(canGoBack: boolean, onBack: () => void): () => void {
  const backButton = getWebApp()?.BackButton
  if (!backButton) return () => undefined

  const handler = (): void => {
    haptic()
    onBack()
  }

  try {
    backButton.offClick?.(handler)
    backButton.onClick(handler)
    if (canGoBack) backButton.show()
    else backButton.hide()
  } catch {
    return () => undefined
  }

  return () => {
    try {
      backButton.offClick?.(handler)
      backButton.hide()
    } catch {
      /* Клиент мог закрыться во время перехода */
    }
  }
}

export function openInvoice(url: string, onClosed: (status: string) => void): boolean {
  const webApp = getWebApp()
  if (!url || !webApp?.openInvoice) return openExternal(url)

  let handled = false
  const finish = (status: string): void => {
    if (handled) return
    handled = true
    try {
      webApp.offEvent?.('invoiceClosed', handler)
    } catch {
      /* Старые клиенты могут не поддерживать offEvent */
    }
    onClosed(status)
  }
  const handler = (data: InvoiceClosed): void => {
    if (!data.url || data.url === url) finish(data.status)
  }

  try {
    webApp.onEvent?.('invoiceClosed', handler)
    webApp.openInvoice(url, (status) => finish(status))
    return true
  } catch {
    try {
      webApp.offEvent?.('invoiceClosed', handler)
    } catch {
      /* Игнорируем ошибку старых клиентов */
    }
    return openExternal(url)
  }
}

export function openExternal(url: string): boolean {
  if (!url) return false
  const webApp = getWebApp()
  const isTelegramLink = /^https?:\/\/(?:t\.me|telegram\.me)\//i.test(url)

  try {
    if (isTelegramLink && webApp?.openTelegramLink) {
      webApp.openTelegramLink(url)
      return true
    }
    if (webApp?.openLink) {
      webApp.openLink(url, { try_instant_view: false })
      return true
    }
  } catch {
    /* Переходим на обычный браузерный fallback */
  }

  try {
    window.location.assign(url)
    return true
  } catch {
    return false
  }
}
