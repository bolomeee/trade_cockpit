import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import { getStockPullbacks } from '@/lib/api/stocks'
import type { PullbackEntry } from '@/types/stockDetail'
import { PullbackHistoryCard } from '@/components/features/stock-detail/PullbackHistoryCard'
import { EmptySymbol } from './EmptySymbol'

export function PullbackWidget() {
  const symbol = useAppStore((s) => s.selectedSymbol)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['pullbacks', symbol],
    queryFn: () => getStockPullbacks(symbol as string),
    enabled: symbol !== null,
    staleTime: 5 * 60 * 1000,
  })

  if (symbol === null) return <EmptySymbol />

  return (
    <div style={{ marginTop: '-5px', marginLeft: '-5px' }}>
      <PullbackHistoryCard
        pullbacks={data as PullbackEntry[] | undefined}
        loading={isLoading}
        error={isError}
        onRetry={() => refetch()}
      />
    </div>
  )
}
