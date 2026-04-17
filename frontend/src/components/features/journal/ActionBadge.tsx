import type { Action } from '@/types/journal'

const BG: Record<Action, string> = {
  BUY: 'var(--color-action-buy)',
  SELL: 'var(--color-action-sell)',
  ADD: 'var(--color-action-add)',
  REDUCE: 'var(--color-action-reduce)',
  WATCH: 'var(--color-action-watch)',
}

export function ActionBadge({ action }: { action: Action }) {
  return (
    <span
      data-testid={`action-badge-${action}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2px 10px',
        borderRadius: 'var(--radius-badge)',
        background: BG[action],
        color: 'var(--color-text-on-dark)',
        fontSize: 'var(--font-size-caption)',
        fontWeight: 'var(--font-weight-medium)',
        lineHeight: 1.4,
      }}
    >
      {action}
    </span>
  )
}
