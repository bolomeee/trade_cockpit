type SetupType =
  | 'BREAKOUT'
  | 'PULLBACK'
  | 'RECLAIM'
  | 'EARNINGS_DRIFT'
  | 'EXTENDED'
  | 'BROKEN'
  | 'NONE'
  | null

const TYPE_COLORS: Record<string, string> = {
  BREAKOUT: 'var(--color-setup-breakout)',
  PULLBACK: 'var(--color-setup-pullback)',
  RECLAIM: 'var(--color-setup-reclaim)',
  EARNINGS_DRIFT: 'var(--color-setup-earnings)',
  EXTENDED: 'var(--color-setup-extended)',
  BROKEN: 'var(--color-setup-broken)',
}

const TYPE_LABELS: Record<string, string> = {
  BREAKOUT: 'BREAKOUT',
  PULLBACK: 'PULLBACK',
  RECLAIM: 'RECLAIM',
  EARNINGS_DRIFT: 'EARN_DRFT',
  EXTENDED: 'EXTENDED',
  BROKEN: 'BROKEN',
}

type Props = { value: SetupType }

export function SetupTypeBadge({ value }: Props) {
  if (!value || value === 'NONE') {
    return (
      <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-badge)' }}>
        —
      </span>
    )
  }

  return (
    <span
      style={{
        color: TYPE_COLORS[value] ?? 'var(--color-text-secondary)',
        fontSize: 'var(--font-size-badge)',
        fontWeight: 'var(--font-weight-medium)',
        letterSpacing: '0.04em',
      }}
    >
      {TYPE_LABELS[value] ?? value}
    </span>
  )
}
