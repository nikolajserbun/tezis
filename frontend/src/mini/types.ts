export interface Config {
  app_name: string
  bot_username: string
  app_env: string
}

export type Tab = 'home' | 'studio' | 'chat' | 'shop' | 'orders' | 'profile'

export type TabFocus = 'referrals' | null

export interface TelegramBackButton {
  show: () => void
  hide: () => void
  onClick: (handler: () => void) => void
  offClick?: (handler: () => void) => void
}

export interface TelegramCloseButton {
  show: () => void
  hide: () => void
  onClick: (handler: () => void) => void
  offClick?: (handler: () => void) => void
}

export interface TelegramHapticFeedback {
  impactOccurred: (type: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void
}

export interface TelegramWebApp {
  initData: string
  ready: () => void
  expand: () => void
  enableClosingConfirmation?: () => void
  setHeaderColor?: (color: string) => void
  setBackgroundColor?: (color: string) => void
  openLink: (url: string, options?: { try_instant_view?: boolean }) => void
  openTelegramLink?: (url: string) => void
  BackButton?: TelegramBackButton
  CloseButton?: TelegramCloseButton
  HapticFeedback?: TelegramHapticFeedback
}

export interface TelegramWebAppWindow extends Window {
  Telegram?: { WebApp?: TelegramWebApp }
}
