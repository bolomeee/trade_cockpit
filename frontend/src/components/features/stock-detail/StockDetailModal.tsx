import { useQueries } from '@tanstack/react-query'
import type { SignalBoardItem } from '@/types/signal'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import {
  getStockFundamentals,
  getStockPullbacks,
} from '@/lib/api/stocks'
import type { Fundamentals, PullbackEntry } from '@/types/stockDetail'
import { StockDetailHeader } from './StockDetailHeader'
import { PullbackHistoryCard } from './PullbackHistoryCard'
import { FundamentalsCard } from './FundamentalsCard'

interface StockDetailModalProps {
  stock: SignalBoardItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const CHART_PLACEHOLDER_HEIGHT = 302

export function StockDetailModal({
  stock,
  open,
  onOpenChange,
}: StockDetailModalProps) {
  const ticker = stock?.ticker ?? null
  const enabled = open && ticker !== null

  const results = useQueries({
    queries: [
      {
        queryKey: ['pullbacks', ticker],
        queryFn: () => getStockPullbacks(ticker as string),
        enabled,
        staleTime: 5 * 60 * 1000,
      },
      {
        queryKey: ['fundamentals', ticker],
        queryFn: () => getStockFundamentals(ticker as string),
        enabled,
        staleTime: 60 * 60 * 1000,
      },
    ],
  })

  const [pullbacksQ, fundamentalsQ] = results

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[1024px]"
        style={{ backgroundColor: 'var(--color-card)' }}
      >
        {stock && (
          <>
            <DialogHeader>
              <DialogTitle asChild>
                <span style={{ position: 'absolute', left: '-9999px' }}>
                  {stock.ticker}
                </span>
              </DialogTitle>
              <DialogDescription asChild>
                <span style={{ position: 'absolute', left: '-9999px' }}>
                  {stock.name}
                </span>
              </DialogDescription>
            </DialogHeader>

            <StockDetailHeader stock={stock} />

            <div
              style={{
                marginTop: 'var(--spacing-4)',
                borderRadius: 'var(--radius-card)',
                border: '1px dashed var(--color-border)',
                backgroundColor: 'var(--color-muted)',
                color: 'var(--color-text-secondary)',
                textAlign: 'center',
                fontSize: 'var(--font-size-caption)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              data-testid="price-chart-placeholder"
            >
              <Skeleton
                style={{
                  width: '100%',
                  height: `${CHART_PLACEHOLDER_HEIGHT}px`,
                  borderRadius: 'var(--radius-card)',
                  position: 'relative',
                }}
              />
              <span style={{ position: 'absolute' }}>
                Price Chart coming in F005-c
              </span>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 644fr) minmax(0, 312fr)',
                gap: 'var(--spacing-4)',
                marginTop: 'var(--spacing-4)',
              }}
            >
              <PullbackHistoryCard
                pullbacks={pullbacksQ.data as PullbackEntry[] | undefined}
                loading={pullbacksQ.isLoading}
                error={pullbacksQ.isError}
                onRetry={() => pullbacksQ.refetch()}
              />
              <FundamentalsCard
                fundamentals={fundamentalsQ.data as Fundamentals | undefined}
                loading={fundamentalsQ.isLoading}
                error={fundamentalsQ.isError}
                onRetry={() => fundamentalsQ.refetch()}
              />
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
