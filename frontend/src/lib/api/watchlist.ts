import { apiFetch } from './client'
import type { WatchlistItem } from '@/types/watchlist'

export function getWatchlist(): Promise<WatchlistItem[]> {
  return apiFetch<WatchlistItem[]>('/watchlist')
}
