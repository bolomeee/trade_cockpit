import type { DataStatus } from './watchlist'

export interface StockSearchItem {
  ticker: string
  name: string
  exchange: string | null
  type: string | null
}

export interface WatchlistCreatedItem {
  id: number
  ticker: string
  name: string
  exchange: string | null
  addedAt: string
  dataStatus: DataStatus
}
