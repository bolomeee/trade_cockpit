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
  getStockChart,
  getStockFundamentals,
  getStockPullbacks,
} from '@/lib/api/stocks'
import type { ChartData, Fundamentals, PullbackEntry } from '@/types/stockDetail'
import { ErrorState } from '@/components/common/ErrorState'
import { StockDetailHeader } from './StockDetailHeader'
import { PriceChart } from './PriceChart'
import { PullbackHistoryCard } from './PullbackHistoryCard'
import { FundamentalsCard } from './FundamentalsCard'

interface StockDetailModalProps {
  stock: SignalBoardItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const CHART_HEIGHT = 302

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
        queryKey: ['chart', ticker],
        queryFn: () => getStockChart(ticker as string),
        enabled,
        staleTime: 5 * 60 * 1000,
      },
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

  const [chartQ, pullbacksQ, fundamentalsQ] = results

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
                border: '1px solid var(--color-border)',
                backgroundColor: 'var(--color-card)',
                overflow: 'hidden',
                minHeight: `${CHART_HEIGHT}px`,
              }}
              data-testid="price-chart-container"
            >
              {chartQ.isLoading && (
                <Skeleton
                  style={{
                    width: '100%',
                    height: `${CHART_HEIGHT}px`,
                    borderRadius: 'var(--radius-card)',
                  }}
                />
              )}
              {chartQ.isError && (
                <div style={{ padding: 'var(--spacing-6)' }}>
                  <ErrorState title="图表加载失败" onRetry={() => chartQ.refetch()} />
                </div>
              )}
              {!chartQ.isLoading && !chartQ.isError && chartQ.data && (
                <PriceChart data={chartQ.data as ChartData} height={CHART_HEIGHT} />
              )}
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
