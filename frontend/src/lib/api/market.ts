import { apiFetch } from './client'
import type { BreakoutSnapshot, MarketIndexItem, SignalType } from '@/types/market'

export function getMarketOverview(): Promise<MarketIndexItem[]> {
  return apiFetch<MarketIndexItem[]>('/market/overview')
}

export function getBreakouts(
  types?: readonly SignalType[],
): Promise<BreakoutSnapshot> {
  const qs = types && types.length > 0 ? `?type=${types.join(',')}` : ''
  return apiFetch<BreakoutSnapshot>(`/market/breakouts${qs}`)
}
