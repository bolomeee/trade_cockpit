import type { SignalType } from '@/types/watchlist'

const BADGE_CONFIG: Record<SignalType, { label: string; bg: string; color: string }> = {
  BREAKOUT:    { label: 'BREAKOUT',    bg: 'var(--color-signal-breakout)',    color: 'var(--color-text-on-dark)' },
  BUY_ZONE:   { label: 'BUY ZONE',    bg: 'var(--color-signal-buyzone)',     color: 'var(--color-text-on-dark)' },
  NEUTRAL:     { label: 'NEUTRAL',     bg: 'var(--color-signal-neutral)',     color: 'var(--color-text-on-dark)' },
  INSUFFICIENT:{ label: 'INSUFFICIENT',bg: 'var(--color-signal-insufficient)',color: 'var(--color-text-primary)' },
}

interface SignalBadgeProps {
  signalType: SignalType | null
  size?: 'sm' | 'md'
}

export function SignalBadge({ signalType, size = 'sm' }: SignalBadgeProps) {
  const type = signalType ?? 'INSUFFICIENT'
  const { label, bg, color } = BADGE_CONFIG[type]
  const fontSize = size === 'sm' ? 'var(--font-size-badge)' : 'var(--font-size-caption)'

  return (
    <span
      style={{
        backgroundColor: bg,
        color,
        borderRadius: 'var(--radius-badge)',
        fontSize,
        fontWeight: 'var(--font-weight-bold)',
        padding: '2px 8px',
        display: 'inline-block',
        whiteSpace: 'nowrap',
        letterSpacing: '0.02em',
      }}
    >
      {label}
    </span>
  )
}
