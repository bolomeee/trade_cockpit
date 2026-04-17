import { apiFetch } from './client'
import type { StockSearchItem } from '@/types/stocks'
import type {
  ChartData,
  Fundamentals,
  PullbackEntry,
} from '@/types/stockDetail'

export function searchStocks(q: string, limit = 10): Promise<StockSearchItem[]> {
  const params = new URLSearchParams({ q, limit: String(limit) })
  return apiFetch<StockSearchItem[]>(`/stocks/search?${params.toString()}`)
}

export function getStockChart(ticker: string): Promise<ChartData> {
  return apiFetch<ChartData>(`/stocks/${encodeURIComponent(ticker)}/chart`)
}

export function getStockPullbacks(ticker: string): Promise<PullbackEntry[]> {
  return apiFetch<PullbackEntry[]>(`/stocks/${encodeURIComponent(ticker)}/pullbacks`)
}

export function getStockFundamentals(ticker: string): Promise<Fundamentals> {
  return apiFetch<Fundamentals>(`/stocks/${encodeURIComponent(ticker)}/fundamentals`)
}
