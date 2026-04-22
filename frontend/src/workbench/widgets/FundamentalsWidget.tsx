import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import { getStockFundamentals } from '@/lib/api/stocks'
import type { Fundamentals } from '@/types/stockDetail'
import { FundamentalsCard } from '@/components/features/stock-detail/FundamentalsCard'
import { EmptySymbol } from './EmptySymbol'

export function FundamentalsWidget() {
  const symbol = useAppStore((s) => s.selectedSymbol)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['fundamentals', symbol],
    queryFn: () => getStockFundamentals(symbol as string),
    enabled: symbol !== null,
    staleTime: 60 * 60 * 1000,
  })

  if (symbol === null) return <EmptySymbol />

  return (
    <div style={{ marginTop: '-5px', marginLeft: '-5px' }}>
      <FundamentalsCard
        fundamentals={data as Fundamentals | undefined}
        loading={isLoading}
        error={isError}
        onRetry={() => refetch()}
      />
    </div>
  )
}
