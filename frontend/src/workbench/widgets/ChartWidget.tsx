import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import { getStockChart } from '@/lib/api/stocks'
import type { ChartData } from '@/types/stockDetail'
import { PriceChart } from '@/components/features/stock-detail/PriceChart'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptySymbol } from './EmptySymbol'

export function ChartWidget() {
  const symbol = useAppStore((s) => s.selectedSymbol)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['chart', symbol],
    queryFn: () => getStockChart(symbol as string),
    enabled: symbol !== null,
    staleTime: 5 * 60 * 1000,
  })

  if (symbol === null) return <EmptySymbol />
  if (isLoading) return <Skeleton style={{ width: '100%', height: '100%' }} />
  if (isError) return <ErrorState title="图表加载失败" onRetry={() => refetch()} />
  if (!data) return null

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <PriceChart data={data as ChartData} />
    </div>
  )
}
