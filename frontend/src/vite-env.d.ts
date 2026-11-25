/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_BOT_USERNAME?: string
  readonly VITE_ADMIN_TELEGRAM_LOGIN?: string
  readonly VITE_DEV_PAYMENTS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
