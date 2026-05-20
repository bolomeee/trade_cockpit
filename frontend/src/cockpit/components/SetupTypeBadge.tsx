type SetupType =
  | 'BREAKOUT'
  | 'RECLAIM'
  | 'EARNINGS_DRIFT'
  | 'EXTENDED'
  | 'BROKEN'
  | 'NONE'
  | 'CAPITULATION'
  | null

const TYPE_COLORS: Record<string, string> = {
  BREAKOUT: 'var(--color-setup-breakout)',
  RECLAIM: 'var(--color-setup-reclaim)',
  EARNINGS_DRIFT: 'var(--color-setup-earnings)',
  EXTENDED: 'var(--color-setup-extended)',
  BROKEN: 'var(--color-setup-broken)',
  CAPITULATION: 'var(--color-setup-capitulation)',
}

const TYPE_LABELS: Record<string, string> = {
  BREAKOUT: 'BREAKOUT',
  RECLAIM: 'RECLAIM',
  EARNINGS_DRIFT: 'EARN_DRFT',
  EXTENDED: 'EXTENDED',
  BROKEN: 'BROKEN',
  CAPITULATION: 'CAP_REV',
}

type Props = { value: SetupType }

export function SetupTypeBadge({ value }: Props) {
  if (value === 'NONE') {
    // detector 已判定，明确"无 setup 形态" — 用斜体小写灰字与"数据缺失"区分
    return (
      <span
        style={{
          color: 'var(--color-text-muted)',
          fontSize: 'var(--font-size-badge)',
          fontStyle: 'italic',
        }}
      >
        none
      </span>
    )
  }
  if (!value) {
    // 字段真缺失（生产几乎不出现） — 保留中划线作为"异常/未知"标记
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
