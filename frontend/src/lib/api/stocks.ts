import { apiFetch } from './client'
import type { StockSearchItem } from '@/types/stocks'

export function searchStocks(q: string, limit = 10): Promise<StockSearchItem[]> {
  const params = new URLSearchParams({ q, limit: String(limit) })
  return apiFetch<StockSearchItem[]>(`/stocks/search?${params.toString()}`)
}
