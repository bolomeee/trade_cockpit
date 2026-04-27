import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getCockpitPool, type PoolFilters, type PoolItem } from '../lib/api/cockpitPoolApi'
import { addStock } from '@/lib/api/watchlist'
import { PoolFilterBar } from './_poolFilterBar'
import { SetupTypeBadge } from '../components/SetupTypeBadge'

const POOL_STALE_TIME_MS = 60_000

type FunnelStep = 'tradable' | 'trend' | 'rs' | 'fundamental' | 'action'

const FUNNEL_STEPS: { key: FunnelStep; label: string }[] = [
  { key: 'tradable', label: 'Tradable' },
  { key: 'trend', label: 'Trend' },
  { key: 'rs', label: 'RS' },
  { key: 'fundamental', label: 'Fund.' },
  { key: 'action', label: 'Action' },
]

const ACTION_COLORS: Record<string, string> = {
  enter: 'var(--color-change-positive)',
  watch: 'var(--color-action-watch)',
  wait: 'var(--color-text-muted)',
  reduce: 'var(--color-action-reduce)',
  exit: 'var(--color-action-sell)',
}

export function PoolBuilderWidget() {
  const [filters, setFilters] = useState<PoolFilters>({})
  const [activeFunnelStep, setActiveFunnelStep] = useState<FunnelStep | null>(null)
  const [addingTickers, setAddingTickers] = useState<Set<string>>(new Set())
  const queryClient = useQueryClient()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['cockpit-pool', filters],
    queryFn: () => getCockpitPool(filters),
    staleTime: POOL_STALE_TIME_MS,
  })

  async function handleAddStock(ticker: string) {
    setAddingTickers((prev) => new Set(prev).add(ticker))
    try {
      await addStock(ticker)
      await queryClient.invalidateQueries({ queryKey: ['cockpit-pool'] })
      await queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    } finally {
      setAddingTickers((prev) => {
        const next = new Set(prev)
        next.delete(ticker)
        return next
      })
    }
  }

  function toggleFunnelStep(step: FunnelStep) {
    setActiveFunnelStep((prev) => (prev === step ? null : step))
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
        fontSize: 'var(--font-size-caption)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '8px 12px',
          borderBottom: '1px solid var(--color-border)',
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontWeight: 'var(--font-weight-medium)',
            color: 'var(--color-text-primary)',
            fontSize: 'var(--font-size-body)',
          }}
        >
          Pool Builder
        </span>
      </div>

      <div
        style={{
          display: 'flex',
          padding: '6px 12px',
          gap: '2px',
          flexShrink: 0,
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        {FUNNEL_STEPS.map(({ key, label }) => (
          <FunnelSegment
            key={key}
            label={label}
            count={data?.funnel[key] ?? 0}
            active={activeFunnelStep === key}
            onToggle={() => toggleFunnelStep(key)}
          />
        ))}
      </div>

      <div style={{ flexShrink: 0, borderBottom: '1px solid var(--color-border)' }}>
        <PoolFilterBar value={filters} onChange={setFilters} />
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 6px' }}>
        {isLoading && (
          <div
            style={{ padding: '16px 12px', color: 'var(--color-text-muted)', textAlign: 'center' }}
          >
            Loading…
          </div>
        )}
        {isError && (
          <div
            style={{
              padding: '16px 12px',
              color: 'var(--color-change-negative)',
              textAlign: 'center',
            }}
          >
            Failed to load pool data
          </div>
        )}
        {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
          <div
            style={{ padding: '16px 12px', color: 'var(--color-text-muted)', textAlign: 'center' }}
          >
            No candidates
          </div>
        )}
        {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
            <thead>
              <tr
                style={{
                  color: 'var(--color-text-muted)',
                  borderBottom: '1px solid var(--color-border)',
                  position: 'sticky',
                  top: 0,
                  zIndex: 1,
                }}
              >
                <Th width="8%">Ticker</Th>
                <Th width="11%">Name</Th>
                <Th width="6%">Sector</Th>
                <Th width="7%">Price</Th>
                <Th width="5%">Trend</Th>
                <Th width="5%">RS</Th>
                <Th width="9%">Setup</Th>
                <Th width="7%">Dist↑</Th>
                <Th width="7%">Dist50</Th>
                <Th width="6%">Earn</Th>
                <Th width="8%">RevGrow</Th>
                <Th width="8%">Action</Th>
                <Th width="5%"></Th>
              </tr>
            </thead>
            <tbody>
              {data!.items.map((item) => (
                <PoolRow
                  key={item.ticker}
                  item={item}
                  isAdding={addingTickers.has(item.ticker)}
                  onAdd={() => handleAddStock(item.ticker)}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function FunnelSegment({
  label,
  count,
  active,
  onToggle,
}: {
  label: string
  count: number
  active: boolean
  onToggle: () => void
}) {
  return (
    <button
      onClick={onToggle}
      aria-pressed={active}
      style={{
        flex: 1,
        padding: '4px 6px',
        cursor: 'pointer',
        textAlign: 'center',
        border: 'none',
        borderRadius: 'var(--radius-sm)',
        background: active ? 'var(--color-muted)' : 'transparent',
        color: 'var(--color-text-muted)',
        fontSize: 'var(--font-size-badge)',
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-family-numeric)',
          fontWeight: 'var(--font-weight-medium)',
          fontSize: 'var(--font-size-caption)',
          color: 'var(--color-text-primary)',
        }}
      >
        {count.toLocaleString('en-US')}
      </div>
      <div>{label}</div>
    </button>
  )
}

function PoolRow({
  item,
  isAdding,
  onAdd,
}: {
  item: PoolItem
  isAdding: boolean
  onAdd: () => void
}) {
  const distStr =
    item.distanceToPivotPct != null
      ? `${item.distanceToPivotPct >= 0 ? '+' : ''}${item.distanceToPivotPct.toFixed(2)}%`
      : '—'
  const dist50Str = item.distanceTo50maPct != null ? `${item.distanceTo50maPct.toFixed(2)}%` : '—'
  const earnStr = item.daysUntilEarnings != null ? `D-${item.daysUntilEarnings}` : '—'
  const revStr = item.revenueGrowthYoy != null ? `${item.revenueGrowthYoy.toFixed(1)}%` : '—'
  const actionColor = item.suggestedAction
    ? (ACTION_COLORS[item.suggestedAction] ?? 'var(--color-text-primary)')
    : 'var(--color-text-muted)'
  const disabled = item.inWatchlist || isAdding

  return (
    <tr
      style={{ borderBottom: '1px solid var(--color-border)' }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLTableRowElement).style.background =
          'var(--color-table-row-hover)'
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLTableRowElement).style.background = 'transparent'
      }}
    >
      <td
        style={{
          ...tdStyle,
          fontFamily: 'var(--font-family-numeric)',
          fontWeight: 'var(--font-weight-medium)',
        }}
      >
        {item.ticker}
      </td>
      <td
        style={{
          ...tdStyle,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={item.name}
      >
        {item.name}
      </td>
      <td style={tdStyle}>{item.sector}</td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>
        ${item.price.toFixed(2)}
      </td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>
        {item.trendScore ?? '—'}
      </td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>
        {item.rsPercentile}
      </td>
      <td style={tdStyle}>
        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        <SetupTypeBadge value={item.setupType as any} />
      </td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>{distStr}</td>
      <td
        style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}
        title={item.earningsDate ?? undefined}
      >
        {dist50Str}
      </td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>{earnStr}</td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>{revStr}</td>
      <td style={{ ...tdStyle, color: actionColor }}>{item.suggestedAction ?? '—'}</td>
      <td style={{ ...tdStyle, textAlign: 'right' }}>
        <button
          onClick={onAdd}
          disabled={disabled}
          aria-label={
            item.inWatchlist ? `${item.ticker} in watchlist` : `Add ${item.ticker}`
          }
          style={{
            fontSize: 'var(--font-size-badge)',
            cursor: disabled ? 'default' : 'pointer',
            color: disabled
              ? 'var(--color-text-muted)'
              : 'var(--color-signal-breakout)',
            background: 'none',
            border: 'none',
            padding: '2px 4px',
          }}
        >
          {item.inWatchlist ? '✓' : isAdding ? '…' : '+ Add'}
        </button>
      </td>
    </tr>
  )
}

function Th({ children, width }: { children: React.ReactNode; width: string }) {
  return (
    <th
      style={{
        padding: '4px 6px',
        textAlign: 'left',
        fontSize: 'var(--font-size-badge)',
        fontWeight: 'var(--font-weight-normal)',
        width,
        background: 'var(--color-card)',
      }}
    >
      {children}
    </th>
  )
}

const tdStyle: React.CSSProperties = {
  padding: '5px 6px',
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-text-primary)',
}
