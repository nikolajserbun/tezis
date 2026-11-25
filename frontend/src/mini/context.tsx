import { createContext, useContext, useEffect } from 'react'
import { useApi } from '../lib/api'
import type { Config, Tab, TabFocus } from './types'
import type { Me } from '../lib/api'

export interface MiniRequestOptions {
  method?: string
  body?: unknown
  auth?: boolean
}

export interface MiniContextValue {
  config: Config
  me: Me
  isDev: boolean
  ordersVersion: number
  notify: (message: string) => void
  haptic: () => void
  run: <T>(path: string, options?: MiniRequestOptions) => Promise<T | null>
  refreshMe: () => void
  bumpOrders: () => void
  go: (tab: Tab, focus?: TabFocus) => void
  signOut: () => void
  handleApiError: (error: unknown) => void
  handleLoadError: (message: string) => void
}

export const MiniContext = createContext<MiniContextValue | null>(null)

export function useMini(): MiniContextValue {
  const context = useContext(MiniContext)
  if (!context) throw new Error('MiniApp context is not available')
  return context
}

export function useMiniApi<T>(path: string | null, deps: unknown[] = []) {
  const { handleLoadError } = useMini()
  const result = useApi<T>(path, deps)

  useEffect(() => {
    if (result.error) handleLoadError(result.error)
  }, [result.error, handleLoadError])

  return result
}
