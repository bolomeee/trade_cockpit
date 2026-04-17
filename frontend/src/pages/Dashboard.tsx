import { useQuery } from '@tanstack/react-query'
import { getWatchlist } from '@/lib/api/watchlist'
import { SignalBoard } from '@/components/features/dashboard/SignalBoard'
import { AddStockCard } from '@/components/features/dashboard/AddStockCard'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'

function LoadingGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} style={{ height: '122px', borderRadius: 'var(--radius-card)' }} />
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    staleTime: 30 * 1000,
  })

  return (
    <div style={{ display: 'flex', gap: 'var(--spacing-6)', padding: 'var(--spacing-8) var(--spacing-6)' }}>
      <div style={{ flex: 1, maxWidth: '871px' }}>
        <h2 style={{ fontSize: 'var(--font-size-title)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-text-primary)', marginBottom: 'var(--spacing-4)' }}>
          SignalBoard
        </h2>

        {isLoading && <LoadingGrid />}

        {isError && (
          <ErrorState onRetry={() => refetch()} />
        )}

        {!isLoading && !isError && data?.length === 0 && (
          <EmptyState title="还没有自选股，从右侧 Add Stock 开始吧" />
        )}

        {!isLoading && !isError && data && data.length > 0 && (
          <SignalBoard stocks={data} onSelectStock={() => {}} />
        )}
      </div>

      <div style={{ width: '158px', flexShrink: 0 }}>
        <AddStockCard />
      </div>
    </div>
  )
}
