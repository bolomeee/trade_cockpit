import type { WatchlistItem } from '@/types/watchlist'
import { SignalBadge } from './SignalBadge'

interface SignalCardProps {
  stock: WatchlistItem
  onClick: () => void
}

export function SignalCard({ stock, onClick }: SignalCardProps) {
  const { ticker, name, latestSignal } = stock

  const distancePct = latestSignal?.distancePct ?? null
  const distanceColor =
    distancePct !== null
      ? distancePct >= 0
        ? 'var(--color-change-positive)'
        : 'var(--color-change-negative)'
      : 'var(--color-text-secondary)'

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={e => e.key === 'Enter' && onClick()}
      style={{
        backgroundColor: 'var(--color-card)',
        borderRadius: 'var(--radius-card)',
        boxShadow: 'var(--shadow-card)',
        border: '1px solid var(--color-border)',
        padding: 'var(--spacing-card-padding-sm)',
        cursor: 'pointer',
        transition: 'box-shadow 150ms ease',
        minHeight: '122px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = 'var(--shadow-hover-card)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = 'var(--shadow-card)')}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
        <span style={{ fontWeight: 'var(--font-weight-bold)', fontSize: 'var(--font-size-subtitle)' }}>
          {ticker}
        </span>
        <SignalBadge signalType={latestSignal?.signalType ?? null} />
      </div>

      <p style={{ fontSize: 'var(--font-size-body)', color: 'var(--color-text-secondary)', margin: '4px 0 0' }}>
        {name}
      </p>

      <div style={{ marginTop: '12px' }}>
        {distancePct !== null ? (
          <span style={{ fontSize: 'var(--font-size-caption)', color: distanceColor, fontFamily: 'var(--font-family-numeric)' }}>
            {distancePct >= 0 ? '+' : ''}{distancePct.toFixed(1)}% MA150
          </span>
        ) : (
          <span style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }}>
            —
          </span>
        )}
      </div>
    </div>
  )
}
