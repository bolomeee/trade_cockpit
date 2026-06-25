import { apiFetch } from './client'

export interface JobFreshness {
  lastAt: string | null
  ageDays: number | null
  stale: boolean
}

export interface RefreshHealth {
  universe: JobFreshness
  breakout: JobFreshness
  poolCacheRows: number
  recentErrors: number
}

export function getRefreshHealth(): Promise<RefreshHealth> {
  return apiFetch<RefreshHealth>('/refresh-health')
}
