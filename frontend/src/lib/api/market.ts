import { apiFetch } from './client'
import type { BreakoutSnapshot, MarketIndexItem } from '@/types/market'

export function getMarketOverview(): Promise<MarketIndexItem[]> {
  return apiFetch<MarketIndexItem[]>('/market/overview')
}

export function getBreakouts(): Promise<BreakoutSnapshot> {
  return apiFetch<BreakoutSnapshot>('/market/breakouts')
}
