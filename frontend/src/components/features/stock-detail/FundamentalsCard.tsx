import type { Fundamentals } from '@/types/stockDetail'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/common/ErrorState'

interface FundamentalsCardProps {
  fundamentals: Fundamentals | undefined
  loading: boolean
  error: boolean
  onRetry: () => void
}

const CARD_STYLE: React.CSSProperties = {
  backgroundColor: 'var(--color-card)',
  borderRadius: 'var(--radius-card)',
  border: '1px solid var(--color-border)',
  padding: 'var(--spacing-4)',
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--spacing-3)',
  minHeight: '314px',
}

const MOCK_BADGE_STYLE: React.CSSProperties = {
  backgroundColor: 'var(--color-signal-insufficient)',
  color: 'var(--color-text-primary)',
  borderRadius: 'var(--radius-badge)',
  fontSize: 'var(--font-size-caption)',
  fontWeight: 'var(--font-weight-bold)',
  padding: '2px 8px',
  marginLeft: '8px',
  letterSpacing: '0.02em',
}

function formatCurrency(value: number): string {
  if (Math.abs(value) >= 1_000_000_000) {
    return `$${(value / 1_000_000_000).toFixed(2)}B`
  }
  if (Math.abs(value) >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(2)}M`
  }
  return `$${value.toFixed(2)}`
}

function Cell({ label, value }: { label: string; value: string }) {
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

function CellSkeleton({ label }: { label: string }) {
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
      <Skeleton style={{ height: '22px', width: '60px' }} />
    </div>
  )
}

export function FundamentalsCard({
  fundamentals,
  loading,
  error,
  onRetry,
}: FundamentalsCardProps) {
  const isMock = fundamentals?.source === 'mock'

  return (
    <section style={CARD_STYLE}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <h3
          style={{
            fontSize: 'var(--font-size-subtitle)',
            fontWeight: 'var(--font-weight-bold)',
            color: 'var(--color-text-primary)',
            margin: 0,
          }}
        >
          Fundamentals
        </h3>
        {isMock && <span style={MOCK_BADGE_STYLE}>Mock Data</span>}
      </div>

      {error && <ErrorState title="基本面加载失败" onRetry={onRetry} />}

      {!error && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: 'var(--spacing-4)',
            marginTop: 'var(--spacing-2)',
          }}
        >
          {loading || !fundamentals ? (
            <>
              <CellSkeleton label="P/E Ratio" />
              <CellSkeleton label="P/S Ratio" />
              <CellSkeleton label="PEG Ratio" />
              <CellSkeleton label="Free Cash Flow" />
            </>
          ) : (
            <>
              <Cell label="P/E Ratio" value={fundamentals.priceToEarnings.toFixed(2)} />
              <Cell label="P/S Ratio" value={fundamentals.priceToSales.toFixed(2)} />
              <Cell label="PEG Ratio" value={fundamentals.peg.toFixed(2)} />
              <Cell
                label="Free Cash Flow"
                value={formatCurrency(fundamentals.freeCashFlow)}
              />
            </>
          )}
        </div>
      )}
    </section>
  )
}
