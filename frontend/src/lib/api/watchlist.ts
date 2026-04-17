import { apiFetch } from './client'
import type { WatchlistItem } from '@/types/watchlist'
import type { WatchlistCreatedItem } from '@/types/stocks'

export function getWatchlist(): Promise<WatchlistItem[]> {
  return apiFetch<WatchlistItem[]>('/watchlist')
}

export function addStock(ticker: string): Promise<WatchlistCreatedItem> {
  return apiFetch<WatchlistCreatedItem>('/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker }),
  })
}

export function removeStock(ticker: string): Promise<{ ticker: string; removed: boolean }> {
  return apiFetch<{ ticker: string; removed: boolean }>(`/watchlist/${encodeURIComponent(ticker)}`, {
    method: 'DELETE',
  })
}
