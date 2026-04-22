import type { WatchlistCreatedItem } from '@/types/stocks'

export type DataStatus = 'loading' | 'insufficient' | 'ready'

export type SignalType = 'BREAKOUT' | 'BUY_ZONE' | 'NEUTRAL' | 'INSUFFICIENT'

export interface LatestSignal {
  signalType: SignalType
  distancePct: number | null
  date: string | null
}

export interface BulkAddResult {
  added: WatchlistCreatedItem[]
  skippedDuplicate: string[]
  notFound: string[]
}

export interface WatchlistItem {
  id: number
  ticker: string
  name: string
  exchange: string | null
  addedAt: string
  lastRefreshedAt: string | null
  dataStatus: DataStatus
  latestSignal: LatestSignal | null
}
