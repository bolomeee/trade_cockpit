import { apiFetch } from './client'

export type RefreshStatus = 'idle' | 'in_progress' | 'completed' | 'failed'
export type RefreshStartStatus = 'started' | 'in_progress'

export interface RefreshProgress {
  total: number
  completed: number
  failed: number
}

export interface RefreshStatusPayload {
  jobId: string | null
  status: RefreshStatus
  progress: RefreshProgress
  startedAt: string | null
  lastRefreshedAt: string | null
}

export interface RefreshStartedPayload {
  jobId: string
  status: RefreshStartStatus
  totalStocks: number
}

export function triggerRefresh(): Promise<RefreshStartedPayload> {
  return apiFetch<RefreshStartedPayload>('/data/refresh', { method: 'POST' })
}

export function getRefreshStatus(): Promise<RefreshStatusPayload> {
  return apiFetch<RefreshStatusPayload>('/data/status')
}
