import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import { getStockChart } from '@/lib/api/stocks'
import { getSignals } from '@/lib/api/signals'
import type { ChartBar, ChartData } from '@/types/stockDetail'
import { PriceChart } from '@/components/features/stock-detail/PriceChart'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/common/ErrorState'
import { formatPercent } from '@/lib/format'
import { EmptySymbol } from './EmptySymbol'

export function ChartWidget() {
  const symbol = useAppStore((s) => s.selectedSymbol)
  const [hoveredBar, setHoveredBar] = useState<ChartBar | null>(null)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['chart', symbol],
    queryFn: () => getStockChart(symbol as string),
    enabled: symbol !== null,
    staleTime: 5 * 60 * 1000,
  })

  const { data: signals } = useQuery({
    queryKey: ['signals'],
    queryFn: getSignals,
    staleTime: 30 * 1000,
  })
  const companyName = signals?.find((s) => s.ticker === symbol)?.name ?? null

  useEffect(() => {
    setHoveredBar(null)
  }, [symbol])

  const displayBar = useMemo<ChartBar | null>(() => {
    if (hoveredBar) return hoveredBar
    const bars = (data as ChartData | undefined)?.bars
    return bars && bars.length > 0 ? bars[bars.length - 1] : null
  }, [hoveredBar, data])

  const volFloatPct = useMemo(() => {
    const sharesFloat = (data as ChartData | undefined)?.sharesFloat
    if (!displayBar || sharesFloat == null || sharesFloat <= 0) return null
    return (displayBar.volume / sharesFloat) * 100
  }, [displayBar, data])

  if (symbol === null) return <EmptySymbol />
  if (isLoading) return <Skeleton style={{ width: '100%', height: '100%' }} />
  if (isError) return <ErrorState title="图表加载失败" onRetry={() => refetch()} />
  if (!data) return null

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: 12,
          zIndex: 2,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          pointerEvents: 'none',
        }}
      >
        <span
          style={{
            fontSize: '18px',
            fontWeight: 'var(--font-weight-bold)',
            color: 'var(--color-text-primary)',
            lineHeight: 1.2,
          }}
        >
          {symbol}
        </span>
        {companyName && (
          <span
            style={{
              fontSize: '14px',
              fontWeight: 'var(--font-weight-regular)',
              color: 'var(--color-text-secondary)',
              lineHeight: 1.2,
            }}
          >
            {companyName}
          </span>
        )}
        <div
          style={{
            marginTop: 4,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            fontSize: 11,
            fontFamily: 'var(--font-family-numeric)',
            lineHeight: 1.2,
          }}
        >
          <span style={{ color: '#f59e0b' }}>— MA5</span>
          <span style={{ color: '#8b5cf6' }}>— MA20</span>
          <span style={{ color: 'var(--color-signal-breakout, #2962ff)' }}>— MA150</span>
          <span style={{ color: 'var(--color-text-secondary)' }}>
            Vol/Float: {formatPercent(volFloatPct)}
          </span>
        </div>
      </div>
      <PriceChart data={data as ChartData} onHoverChange={setHoveredBar} />
    </div>
  )
}
