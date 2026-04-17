import { ACTIONS, type Action, type JournalFilter } from '@/types/journal'

interface Props {
  filter: JournalFilter
  onChange: (next: JournalFilter) => void
  tickerOptions: string[]
}

const selectStyle: React.CSSProperties = {
  padding: '8px 12px',
  borderRadius: 'var(--radius-select)',
  border: '1px solid var(--color-border)',
  background: 'var(--color-card)',
  fontSize: 'var(--font-size-body)',
  color: 'var(--color-text-primary)',
  minWidth: '160px',
}

export function JournalFilterCard({ filter, onChange, tickerOptions }: Props) {
  const hasFilter = !!(filter.ticker || filter.action)

  return (
    <div
      style={{
        background: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-card)',
        padding: '17px',
        display: 'flex',
        gap: 'var(--spacing-4)',
        alignItems: 'center',
        flexWrap: 'wrap',
      }}
    >
      <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <span style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }}>
          Ticker
        </span>
        <select
          style={selectStyle}
          value={filter.ticker ?? ''}
          onChange={(e) =>
            onChange({ ...filter, ticker: e.target.value || undefined })
          }
        >
          <option value="">All</option>
          {tickerOptions.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <span style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }}>
          Action
        </span>
        <select
          style={selectStyle}
          value={filter.action ?? ''}
          onChange={(e) =>
            onChange({ ...filter, action: (e.target.value || undefined) as Action | undefined })
          }
        >
          <option value="">All</option>
          {ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        onClick={() => onChange({})}
        disabled={!hasFilter}
        style={{
          marginLeft: 'auto',
          alignSelf: 'flex-end',
          padding: '8px 16px',
          borderRadius: 'var(--radius-button)',
          border: '1px solid var(--color-border)',
          background: 'transparent',
          fontSize: 'var(--font-size-body)',
          color: hasFilter ? 'var(--color-text-primary)' : 'var(--color-text-placeholder)',
          cursor: hasFilter ? 'pointer' : 'not-allowed',
        }}
      >
        Clear Filters
      </button>
    </div>
  )
}
