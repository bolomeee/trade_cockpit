import { apiFetch } from '@/lib/api/client'

export const POOL_TIMEOUT_MS = 60_000

export type PoolFilters = {
  marketCapMin?: number
  priceMin?: number
  advMin?: number
  trendScoreMin?: number
  rsPercentileMin?: number
  revenueGrowthYoyMin?: number
  sectors?: string
  setupTypes?: string
  limit?: number
}

export type PoolFunnel = {
  tradable: number
  trend: number
  rs: number
  fundamental: number
  action: number
}

export type PoolItem = {
  ticker: string
  name: string
  sector: string
  price: number
  trendScore: number | null
  rsPercentile: number
  setupType: 'BREAKOUT' | 'RECLAIM' | 'EARNINGS_DRIFT' | 'EXTENDED' | 'BROKEN' | 'NONE' | null
  distanceToPivotPct: number | null
  distanceTo50maPct: number | null
  earningsDate: string | null
  daysUntilEarnings: number | null
  revenueGrowthYoy: number | null
  suggestedAction: string | null
  inWatchlist: boolean
}

export type PoolData = {
  funnel: PoolFunnel
  items: PoolItem[]
}

export function getCockpitPool(filters: PoolFilters = {}): Promise<PoolData> {
  const params = new URLSearchParams()
  if (filters.marketCapMin != null) params.set('marketCapMin', String(filters.marketCapMin))
  if (filters.priceMin != null) params.set('priceMin', String(filters.priceMin))
  if (filters.advMin != null) params.set('advMin', String(filters.advMin))
  if (filters.trendScoreMin != null) params.set('trendScoreMin', String(filters.trendScoreMin))
  if (filters.rsPercentileMin != null) params.set('rsPercentileMin', String(filters.rsPercentileMin))
  if (filters.revenueGrowthYoyMin != null) params.set('revenueGrowthYoyMin', String(filters.revenueGrowthYoyMin))
  if (filters.sectors) params.set('sectors', filters.sectors)
  if (filters.setupTypes) params.set('setupTypes', filters.setupTypes)
  if (filters.limit != null) params.set('limit', String(filters.limit))

  const qs = params.toString() ? `?${params.toString()}` : ''

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), POOL_TIMEOUT_MS)

  return apiFetch<PoolData>(`/cockpit/pool${qs}`, { signal: controller.signal }).finally(() => {
    clearTimeout(timer)
  })
}
