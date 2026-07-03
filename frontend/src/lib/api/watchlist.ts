import { apiFetch } from './client'
import type { BulkAddResult, WatchlistItem } from '@/types/watchlist'
import type { WatchlistCreatedItem } from '@/types/stocks'
import type { LabelColor } from '@/types/signal'

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

export function bulkAddStocks(tickers: string[]): Promise<BulkAddResult> {
  return apiFetch<BulkAddResult>('/watchlist/bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers }),
  })
}

export function updateColor(
  ticker: string,
  color: LabelColor,
): Promise<{ ticker: string; labelColor: LabelColor }> {
  return apiFetch<{ ticker: string; labelColor: LabelColor }>(`/watchlist/${encodeURIComponent(ticker)}/color`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ color }),
  })
}
