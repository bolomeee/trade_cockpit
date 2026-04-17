import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getSignals } from '@/lib/api/signals'
import type { SignalBoardItem } from '@/types/signal'
import { SignalBoard } from '@/components/features/dashboard/SignalBoard'
import { AddStockCard } from '@/components/features/dashboard/AddStockCard'
import { StockDetailModal } from '@/components/features/stock-detail/StockDetailModal'
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
    queryKey: ['signals'],
    queryFn: getSignals,
    staleTime: 30 * 1000,
  })

  const [selected, setSelected] = useState<SignalBoardItem | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  const handleSelect = (stock: SignalBoardItem) => {
    setSelected(stock)
    setModalOpen(true)
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: 'var(--spacing-6)',
        padding: 'var(--spacing-8) var(--spacing-6)',
        maxWidth: '1053px',
        marginInline: 'auto',
        alignItems: 'flex-start',
      }}
    >
      <div style={{ flex: 1, maxWidth: '871px' }}>
        <h2
          style={{
            fontSize: 'var(--font-size-title)',
            fontWeight: 'var(--font-weight-bold)',
            color: 'var(--color-text-primary)',
            margin: 0,
            marginBottom: 'var(--spacing-4)',
          }}
        >
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
          <SignalBoard stocks={data} onSelectStock={handleSelect} />
        )}
      </div>

      <div style={{ width: '158px', flexShrink: 0 }}>
        <AddStockCard />
      </div>

      <StockDetailModal stock={selected} open={modalOpen} onOpenChange={setModalOpen} />
    </div>
  )
}
