import { LOG_LEVEL_FILTERS, type LogLevelFilterValue } from '@/types/log'

interface LogLevelFilterProps {
  value: LogLevelFilterValue
  onChange: (next: LogLevelFilterValue) => void
}

export function LogLevelFilter({ value, onChange }: LogLevelFilterProps) {
  return (
    <div style={{ display: 'inline-flex', gap: '8px' }}>
      {LOG_LEVEL_FILTERS.map((v) => {
        const active = v === value
        return (
          <button
            key={v}
            type="button"
            onClick={() => onChange(v)}
            style={{
              padding: '6px 14px',
              borderRadius: '9999px',
              border: '1px solid var(--color-border)',
              background: active ? 'var(--color-text-primary)' : 'transparent',
              color: active ? 'var(--color-text-on-dark)' : 'var(--color-text-primary)',
              fontSize: 'var(--font-size-body)',
              fontWeight: active ? 'var(--font-weight-medium)' : 'var(--font-weight-regular)',
              cursor: 'pointer',
            }}
          >
            {v}
          </button>
        )
      })}
    </div>
  )
}
