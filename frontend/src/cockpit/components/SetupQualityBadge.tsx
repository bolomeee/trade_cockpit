type SetupQuality = 'A' | 'B' | 'C' | null

const QUALITY_COLORS: Record<string, string> = {
  A: 'var(--color-setup-quality-a)',
  B: 'var(--color-setup-quality-b)',
  C: 'var(--color-setup-quality-c)',
}

type Props = { value: SetupQuality }

export function SetupQualityBadge({ value }: Props) {
  if (!value) {
    return (
      <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-badge)' }}>
        —
      </span>
    )
  }

  return (
    <span
      style={{
        color: QUALITY_COLORS[value] ?? 'var(--color-text-secondary)',
        fontSize: 'var(--font-size-badge)',
        fontWeight: 'var(--font-weight-bold)',
      }}
    >
      {value}
    </span>
  )
}
