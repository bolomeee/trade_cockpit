import type { ActionItem, ActionType } from '../lib/api/cockpitActionsApi'

export type ActionSectionVariant = 'must' | 'monitor' | 'noaction'

const SECTION_TITLE: Record<ActionSectionVariant, string> = {
  must: 'Must Act',
  monitor: 'Monitor',
  noaction: 'No Action',
}

const SECTION_BG: Record<ActionSectionVariant, string> = {
  must: 'var(--color-action-must-bg)',
  monitor: 'var(--color-action-monitor-bg)',
  noaction: 'var(--color-action-noaction-bg)',
}

const ACTION_LABEL: Record<ActionType, string> = {
  raise_stop: 'Raise Stop',
  cancel_order: 'Cancel Order',
  reduce_before_earnings: 'Reduce (Earnings)',
  tighten_stop: 'Tighten Stop',
  approaching_trigger: 'Approaching Trigger',
  stable_position: 'Stable',
}

type Props = {
  variant: ActionSectionVariant
  items: ActionItem[]
  onTickerClick: (ticker: string) => void
}

export function ActionListSection({ variant, items, onTickerClick }: Props) {
  if (items.length === 0) return null

  return (
    <section
      data-testid={`action-section-${variant}`}
      style={{
        background: SECTION_BG[variant],
        borderRadius: '4px',
        padding: '8px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}
    >
      <div
        style={{
          fontSize: 'var(--font-size-caption)',
          fontWeight: 'var(--font-weight-medium)',
          color: 'var(--color-text-secondary)',
        }}
      >
        {SECTION_TITLE[variant]} ({items.length})
      </div>
      {items.map((item, idx) => (
        <div
          key={`${item.ticker}-${item.actionType}-${idx}`}
          data-testid={`action-row-${variant}-${item.ticker}`}
          onClick={() => onTickerClick(item.ticker)}
          title={`${item.rationale}\n\n${JSON.stringify(item.refs)}`}
          style={{
            display: 'grid',
            gridTemplateColumns: '60px 160px 1fr',
            gap: '8px',
            alignItems: 'baseline',
            padding: '2px 0',
            cursor: 'pointer',
            fontSize: 'var(--font-size-caption)',
          }}
        >
          <span style={{ fontWeight: 'var(--font-weight-medium)' }}>{item.ticker}</span>
          <span style={{ color: 'var(--color-text-secondary)' }}>{ACTION_LABEL[item.actionType]}</span>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {item.rationale}
          </span>
        </div>
      ))}
    </section>
  )
}
