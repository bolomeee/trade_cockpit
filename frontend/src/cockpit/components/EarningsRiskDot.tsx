type EarningsRisk = 'SAFE' | 'CAUTION' | 'DANGER' | null

const RISK_COLORS: Record<string, string> = {
  SAFE: 'var(--color-earnings-safe)',
  CAUTION: 'var(--color-earnings-caution)',
  DANGER: 'var(--color-earnings-danger)',
}

type Props = {
  value: EarningsRisk
  daysUntil?: number | null
}

export function EarningsRiskDot({ value, daysUntil }: Props) {
  if (!value) return null

  const color = RISK_COLORS[value] ?? 'var(--color-text-muted)'

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
      <span
        style={{
          display: 'inline-block',
          width: '7px',
          height: '7px',
          borderRadius: '50%',
          backgroundColor: color,
          flexShrink: 0,
        }}
      />
      {value === 'DANGER' && daysUntil != null && (
        <span
          style={{
            color,
            fontSize: 'var(--font-size-badge)',
            fontWeight: 'var(--font-weight-medium)',
          }}
        >
          D-{daysUntil}
        </span>
      )}
    </span>
  )
}
