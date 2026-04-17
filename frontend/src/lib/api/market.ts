import { apiFetch } from './client'
import type { MarketIndexItem } from '@/types/market'

export function getMarketOverview(): Promise<MarketIndexItem[]> {
  return apiFetch<MarketIndexItem[]>('/market/overview')
}
