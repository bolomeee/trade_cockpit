import { useQuery } from '@tanstack/react-query'

import { getMarketOverview } from '@/lib/api/market'

export const MARKET_OVERVIEW_KEY = ['market', 'overview'] as const

export function useMarketOverview() {
  return useQuery({
    queryKey: MARKET_OVERVIEW_KEY,
    queryFn: getMarketOverview,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })
}
