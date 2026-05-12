import { useState, useEffect, useRef } from 'react'
import type { PoolFilters } from '../lib/api/cockpitPoolApi'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const FILTER_DEBOUNCE_MS = 300

type Props = {
  value: PoolFilters
  onChange: (next: PoolFilters) => void
  availableSectors?: string[]
}

export function PoolFilterBar({ value, onChange, availableSectors = [] }: Props) {
  const [local, setLocal] = useState<PoolFilters>(value)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function update(patch: Partial<PoolFilters>) {
    const next = { ...local, ...patch }
    setLocal(next)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => onChange(next), FILTER_DEBOUNCE_MS)
  }

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    },
    [],
  )

  return (
    <div
      style={{
        display: 'flex',
        gap: '8px',
        flexWrap: 'wrap',
        alignItems: 'center',
        padding: '6px 12px',
      }}
    >
      <Field label="MktCap≥" id="pool-mcap">
        <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
          <Input
            id="pool-mcap"
            type="number"
            value={local.marketCapMin != null ? local.marketCapMin / 1_000_000_000 : ''}
            onChange={(e) =>
              update({ marketCapMin: e.target.value ? Number(e.target.value) * 1_000_000_000 : undefined })
            }
            style={{ ...inputStyle(60), paddingRight: '14px' }}
            placeholder="10"
          />
          <span style={{
            position: 'absolute',
            right: '5px',
            fontSize: 'var(--font-size-badge)',
            color: 'var(--color-text-muted)',
            pointerEvents: 'none',
          }}>B</span>
        </div>
      </Field>
      <Field label="Price≥" id="pool-price">
        <Input
          id="pool-price"
          type="number"
          value={local.priceMin ?? ''}
          onChange={(e) =>
            update({ priceMin: e.target.value ? Number(e.target.value) : undefined })
          }
          style={inputStyle(60)}
          placeholder="10"
        />
      </Field>
      <Field label="ADV≥" id="pool-adv">
        <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
          <Input
            id="pool-adv"
            type="number"
            value={local.advMin != null ? local.advMin / 1_000_000 : ''}
            onChange={(e) =>
              update({ advMin: e.target.value ? Number(e.target.value) * 1_000_000 : undefined })
            }
            style={{ ...inputStyle(60), paddingRight: '14px' }}
            placeholder="20"
          />
          <span style={{
            position: 'absolute',
            right: '5px',
            fontSize: 'var(--font-size-badge)',
            color: 'var(--color-text-muted)',
            pointerEvents: 'none',
          }}>M</span>
        </div>
      </Field>
      <Field label="Trend≥" id="pool-trend">
        <Input
          id="pool-trend"
          type="number"
          value={local.trendScoreMin ?? ''}
          onChange={(e) =>
            update({ trendScoreMin: e.target.value ? Number(e.target.value) : undefined })
          }
          style={inputStyle(50)}
          placeholder="3"
        />
      </Field>
      <Field label="RS≥" id="pool-rs">
        <Input
          id="pool-rs"
          type="number"
          value={local.rsPercentileMin ?? ''}
          onChange={(e) =>
            update({ rsPercentileMin: e.target.value ? Number(e.target.value) : undefined })
          }
          style={inputStyle(50)}
          placeholder="70"
        />
      </Field>
      <Field label="RevGrow≥" id="pool-rev">
        <Input
          id="pool-rev"
          type="number"
          value={local.revenueGrowthYoyMin ?? ''}
          onChange={(e) =>
            update({ revenueGrowthYoyMin: e.target.value ? Number(e.target.value) : undefined })
          }
          style={inputStyle(60)}
          placeholder="10"
        />
      </Field>
      <Field label="Sector" id="pool-sectors">
        <select
          id="pool-sectors"
          value={local.sectors ?? ''}
          onChange={(e) => update({ sectors: e.target.value || undefined })}
          style={{
            ...inputStyle(110),
            textAlign: 'left',
            cursor: 'pointer',
            background: 'transparent',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            color: local.sectors ? 'var(--color-text-primary)' : 'var(--color-text-muted)',
          }}
        >
          <option value="">All</option>
          {availableSectors.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </Field>
      <Field label="Setup" id="pool-setups">
        <Input
          id="pool-setups"
          type="text"
          value={local.setupTypes ?? ''}
          onChange={(e) => update({ setupTypes: e.target.value || undefined })}
          style={inputStyle(100)}
          placeholder="BREAKOUT"
        />
      </Field>
      <Field label="Limit" id="pool-limit">
        <Input
          id="pool-limit"
          type="number"
          value={local.limit ?? ''}
          onChange={(e) =>
            update({ limit: e.target.value ? Number(e.target.value) : undefined })
          }
          style={inputStyle(55)}
          placeholder="50"
        />
      </Field>
    </div>
  )
}

function inputStyle(width: number): React.CSSProperties {
  return { width: `${width}px`, fontSize: 'var(--font-size-badge)', padding: '2px 5px', height: '22px', textAlign: 'center' }
}

function Field({
  label,
  id,
  children,
}: {
  label: string
  id: string
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
      <Label
        htmlFor={id}
        style={{
          fontSize: 'var(--font-size-badge)',
          color: 'var(--color-text-muted)',
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </Label>
      {children}
    </div>
  )
}
