import { apiFetch } from './client'
import type { LogEntry, LogLevel } from '@/types/log'

export interface GetLogsParams {
  level?: LogLevel
  limit?: number
}

export function getLogs(params?: GetLogsParams): Promise<LogEntry[]> {
  const qs = new URLSearchParams()
  if (params?.level) qs.set('level', params.level)
  if (params?.limit) qs.set('limit', String(params.limit))
  const s = qs.toString()
  return apiFetch<LogEntry[]>(`/logs${s ? `?${s}` : ''}`)
}
