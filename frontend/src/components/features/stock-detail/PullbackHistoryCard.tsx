import type { PullbackEntry } from '@/types/stockDetail'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/common/ErrorState'

interface PullbackHistoryCardProps {
  pullbacks: PullbackEntry[] | undefined
  loading: boolean
  error: boolean
  onRetry: () => void
}

function formatDistance(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatReturn(value: number | null): { text: string; color: string } {
  if (value === null) {
    return { text: '—', color: 'var(--color-text-secondary)' }
  }
  const sign = value >= 0 ? '+' : ''
  const color =
    value >= 0 ? 'var(--color-change-positive)' : 'var(--color-change-negative)'
  return { text: `${sign}${value.toFixed(2)}%`, color }
}

function distanceColor(value: number): string {
  return value < 0
    ? 'var(--color-change-negative)'
    : 'var(--color-text-primary)'
}

export function PullbackHistoryCard({
  pullbacks,
  loading,
  error,
  onRetry,
}: PullbackHistoryCardProps) {
  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} style={{ height: '28px' }} />
        ))}
      </div>
    )
  }

  if (error) return <ErrorState title="回踩记录加载失败" onRetry={onRetry} />

  if (!pullbacks || pullbacks.length === 0) {
    return (
      <p
        style={{
          color: 'var(--color-text-secondary)',
          fontSize: 'var(--font-size-body)',
          textAlign: 'center',
          padding: 'var(--spacing-6) 0',
        }}
      >
        No pullbacks yet
      </p>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 'var(--font-size-body)',
          fontFamily: 'var(--font-family-numeric)',
        }}
      >
        <thead>
          <tr style={{ color: 'var(--color-text-secondary)' }}>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Date</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>Distance</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>10D</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>20D</th>
            <th style={{ textAlign: 'right', padding: '6px 8px' }}>30D</th>
          </tr>
        </thead>
        <tbody>
          {pullbacks.map((p) => {
            const r10 = formatReturn(p.return10d)
            const r20 = formatReturn(p.return20d)
            const r30 = formatReturn(p.return30d)
            return (
              <tr
                key={p.date}
                style={{ borderTop: '1px solid var(--color-border)' }}
              >
                <td style={{ padding: '8px', color: 'var(--color-text-primary)' }}>
                  {p.date}
                </td>
                <td
                  style={{
                    padding: '8px',
                    textAlign: 'right',
                    color: distanceColor(p.distancePct),
                  }}
                >
                  {formatDistance(p.distancePct)}
                </td>
                <td style={{ padding: '8px', textAlign: 'right', color: r10.color }}>
                  {r10.text}
                </td>
                <td style={{ padding: '8px', textAlign: 'right', color: r20.color }}>
                  {r20.text}
                </td>
                <td style={{ padding: '8px', textAlign: 'right', color: r30.color }}>
                  {r30.text}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
