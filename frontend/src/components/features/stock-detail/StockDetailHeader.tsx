import type { SignalBoardItem } from '@/types/signal'
import { SignalBadge } from '@/components/features/dashboard/SignalBadge'
import { Skeleton } from '@/components/ui/skeleton'

interface StockDetailHeaderProps {
  stock: SignalBoardItem
  loading?: boolean
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      <span
        style={{
          fontSize: 'var(--font-size-caption)',
          color: 'var(--color-text-secondary)',
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: 'var(--font-size-subtitle)',
          fontWeight: 'var(--font-weight-bold)',
          fontFamily: 'var(--font-family-numeric)',
          color: 'var(--color-text-primary)',
        }}
      >
        {value}
      </span>
    </div>
  )
}

function MetricSkeleton({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <span
        style={{
          fontSize: 'var(--font-size-caption)',
          color: 'var(--color-text-secondary)',
        }}
      >
        {label}
      </span>
      <Skeleton style={{ height: '22px', width: '80px' }} />
    </div>
  )
}

function formatPrice(value: number | null): string {
  return value !== null ? `$${value.toFixed(2)}` : '—'
}

function formatDistance(value: number | null): string {
  if (value === null) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

function formatSlope(positive: boolean | null): string {
  if (positive === null) return '—'
  return positive ? '↑ UP' : '↓ DOWN'
}

export function StockDetailHeader({ stock, loading }: StockDetailHeaderProps) {
  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--spacing-3)',
        }}
      >
        <h1
          style={{
            fontSize: 'var(--font-size-hero)',
            fontWeight: 'var(--font-weight-bold)',
            margin: 0,
          }}
        >
          {stock.ticker}
        </h1>
        <SignalBadge signalType={stock.signalType} size="md" />
      </div>
      <p
        style={{
          color: 'var(--color-text-secondary)',
          margin: '4px 0 0 0',
          fontSize: 'var(--font-size-body)',
        }}
      >
        {stock.name}
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
          gap: 'var(--spacing-4)',
          marginTop: 'var(--spacing-4)',
        }}
      >
        {loading ? (
          <>
            <MetricSkeleton label="Close Price" />
            <MetricSkeleton label="MA150" />
            <MetricSkeleton label="Distance" />
            <MetricSkeleton label="Slope" />
          </>
        ) : (
          <>
            <Metric label="Close Price" value={formatPrice(stock.closePrice)} />
            <Metric label="MA150" value={formatPrice(stock.ma150Value)} />
            <Metric label="Distance" value={formatDistance(stock.distancePct)} />
            <Metric label="Slope" value={formatSlope(stock.slopePositive)} />
          </>
        )}
      </div>
    </div>
  )
}
