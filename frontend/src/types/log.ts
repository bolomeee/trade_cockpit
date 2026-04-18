export type LogLevel = 'OK' | 'INFO' | 'WARN' | 'ERROR'

export const LOG_LEVELS: LogLevel[] = ['OK', 'INFO', 'WARN', 'ERROR']

export type LogLevelFilterValue = 'ALL' | LogLevel

export const LOG_LEVEL_FILTERS: LogLevelFilterValue[] = ['ALL', 'OK', 'INFO', 'WARN', 'ERROR']

export interface LogEntry {
  id: number
  level: LogLevel
  source: string
  message: string
  detail: string | null
  createdAt: string
}
