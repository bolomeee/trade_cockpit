import { useQuery } from '@tanstack/react-query'
import { getSignals } from '@/lib/api/signals'
import { useAppStore } from '@/store/useAppStore'
import { SignalBoard } from '@/components/features/dashboard/SignalBoard'
import { AddStockCard } from '@/components/features/dashboard/AddStockCard'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'

export function WatchlistWidget() {
  const setSelectedSymbol = useAppStore((s) => s.setSelectedSymbol)
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['signals'],
    queryFn: getSignals,
    staleTime: 30 * 1000,
  })

  return (
    <div className="flex h-full flex-col gap-4">
      <AddStockCard />
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} style={{ height: '122px', borderRadius: 'var(--radius-card)' }} />
          ))}
        </div>
      )}
      {isError && <ErrorState onRetry={() => refetch()} />}
      {!isLoading && !isError && data?.length === 0 && (
        <EmptyState title="还没有自选股，上方 Add Stock 添加一只吧" />
      )}
      {!isLoading && !isError && data && data.length > 0 && (
        <SignalBoard stocks={data} onSelectStock={(s) => setSelectedSymbol(s.ticker)} />
      )}
    </div>
  )
}
