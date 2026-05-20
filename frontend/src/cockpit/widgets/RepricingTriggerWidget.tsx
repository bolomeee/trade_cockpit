import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useCockpitStore } from '@/store/cockpitStore'
import {
  getAllActiveTriggers,
  type TriggerType,
  type RepricingTrigger,
  type EarningsAccelEvidence,
  type MarginExpansionEvidence,
  type NewProductEvidence,
  type SectorCycleEvidence,
  type BalanceInflectionEvidence,
} from '../lib/api/cockpitRepricingApi'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// eslint-disable-next-line react-refresh/only-export-components
export const TRIGGER_COLOR_TOKEN: Record<TriggerType, string> = {
  EARNINGS_ACCEL: 'var(--color-trigger-earnings-accel)',
  MARGIN_EXPANSION: 'var(--color-trigger-margin-expansion)',
  NEW_PRODUCT: 'var(--color-trigger-new-product)',
  SECTOR_CYCLE: 'var(--color-trigger-sector-cycle)',
  BALANCE_INFLECTION: 'var(--color-trigger-balance-inflection)',
}

const TRIGGER_SHORT_LABELS: Record<TriggerType, string> = {
  EARNINGS_ACCEL: 'EarningsAccel',
  MARGIN_EXPANSION: 'MarginExp',
  NEW_PRODUCT: 'NewProduct',
  SECTOR_CYCLE: 'SectorCycle',
  BALANCE_INFLECTION: 'BalanceInflect',
}

type FilterValue = 'all' | TriggerType

const FILTER_OPTIONS: Array<{ value: FilterValue; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'EARNINGS_ACCEL', label: 'EarningsAccel' },
  { value: 'MARGIN_EXPANSION', label: 'MarginExp' },
  { value: 'NEW_PRODUCT', label: 'NewProduct' },
  { value: 'SECTOR_CYCLE', label: 'SectorCycle' },
  { value: 'BALANCE_INFLECTION', label: 'BalanceInflect' },
]

// eslint-disable-next-line react-refresh/only-export-components
export function summarizeEvidence(t: RepricingTrigger): string {
  switch (t.triggerType) {
    case 'EARNINGS_ACCEL': {
      const ev = t.evidence as EarningsAccelEvidence
      const last = ev.epsYoyGrowth.at(-1) ?? 0
      return `eps yoy ${Math.round(last)}%`
    }
    case 'MARGIN_EXPANSION': {
      const ev = t.evidence as MarginExpansionEvidence
      return `${ev.triggerMetric} +${ev.expansionBp}bp`
    }
    case 'NEW_PRODUCT': {
      const ev = t.evidence as NewProductEvidence
      const n = Object.keys(ev.keywordHits).length
      const m = ev.newsLinks.length
      return `${n} keywords / ${m} news`
    }
    case 'SECTOR_CYCLE': {
      const ev = t.evidence as SectorCycleEvidence
      const first = ev.rsHistory[0] ?? 0
      const last = ev.rsHistory.at(-1) ?? 0
      return `${ev.sector} RS ${Math.round(first)}→${Math.round(last)}`
    }
    case 'BALANCE_INFLECTION': {
      const ev = t.evidence as BalanceInflectionEvidence
      if (ev.triggerMetric === 'fcf') {
        const first = ev.fcfTrend[0] ?? 0
        const last = ev.fcfTrend.at(-1) ?? 0
        if (first < 0 && last >= 0) return 'fcf flip +'
        const pct =
          first !== 0
            ? Math.abs(Math.round(((last - first) / Math.abs(first)) * 100))
            : 0
        return `fcf ↓ ${pct}%`
      } else {
        const trend = ev.netDebtTrend
        const first = trend[0] ?? 0
        const last = trend.at(-1) ?? 0
        const pct =
          first !== 0
            ? Math.abs(Math.round(((first - last) / Math.abs(first)) * 100))
            : 0
        return `net_debt ↓ ${pct}%`
      }
    }
  }
}

export function RepricingTriggerWidget() {
  const [filterValue, setFilterValue] = useState<FilterValue>('all')
  const [spinning, setSpinning] = useState(false)
  const setSelectedTicker = useCockpitStore((s) => s.setSelectedTicker)

  const triggerType = filterValue === 'all' ? undefined : filterValue

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['cockpit-repricing-all', triggerType],
    queryFn: () => getAllActiveTriggers({ triggerType }),
    staleTime: 5 * 60 * 1000,
  })

  async function handleRefresh() {
    setSpinning(true)
    await Promise.all([refetch(), new Promise((r) => setTimeout(r, 600))])
    setSpinning(false)
  }

  const totalCount = data?.totalCount ?? 0
  const triggers = data?.triggers ?? []
  const showTruncated = data != null && triggers.length < totalCount

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
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          borderBottom: '1px solid var(--color-border)',
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontWeight: 'var(--font-weight-medium)',
            color: 'var(--color-text-primary)',
            flexShrink: 0,
          }}
        >
          Repricing Triggers
          {data != null && (
            <span style={{ color: 'var(--color-text-muted)', fontWeight: 'normal' }}>
              {' '}· {totalCount} active
            </span>
          )}
        </span>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Select value={filterValue} onValueChange={(v) => setFilterValue(v as FilterValue)}>
            <SelectTrigger className="h-6 text-xs" style={{ minWidth: '110px' }}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {FILTER_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value} className="text-xs">
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <button
            type="button"
            aria-label="Refresh repricing triggers"
            onClick={handleRefresh}
            disabled={spinning}
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '2px 4px',
              border: 'none',
              background: 'none',
              cursor: spinning ? 'default' : 'pointer',
              color: 'var(--color-text-muted)',
              flexShrink: 0,
            }}
          >
            <RefreshCw size={13} className={spinning ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 6px' }}>
        {isLoading && (
          <div
            style={{
              padding: '16px 12px',
              color: 'var(--color-text-muted)',
              textAlign: 'center',
            }}
          >
            Loading…
          </div>
        )}

        {isError && (
          <div style={{ padding: '16px 12px', textAlign: 'center' }}>
            <p style={{ color: 'var(--color-text-secondary)', margin: '0 0 8px' }}>
              加载失败，请稍后重试
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              style={{
                fontSize: 'var(--font-size-caption)',
                color: 'var(--color-text-muted)',
                border: '1px solid var(--color-border)',
                borderRadius: '4px',
                background: 'none',
                padding: '2px 8px',
                cursor: 'pointer',
              }}
            >
              重试
            </button>
          </div>
        )}

        {!isLoading && !isError && data != null && totalCount === 0 && (
          <div
            style={{
              padding: '16px 12px',
              color: 'var(--color-text-secondary)',
              textAlign: 'center',
            }}
          >
            今日全市场无 active trigger（cron 每日 22:40 UTC 后刷新）
          </div>
        )}

        {!isLoading && !isError && triggers.length > 0 && (
          <>
            <table
              style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}
            >
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
                  <Th width="14%">Ticker</Th>
                  <Th width="24%">Trigger</Th>
                  <Th width="20%">Date</Th>
                  <Th width="12%">Conf</Th>
                  <Th width="30%">Evidence</Th>
                </tr>
              </thead>
              <tbody>
                {triggers.map((t, i) => (
                  <TriggerRow
                    key={`${t.ticker}-${t.triggerType}-${i}`}
                    trigger={t}
                    onClick={() => setSelectedTicker(t.ticker)}
                  />
                ))}
              </tbody>
            </table>

            {showTruncated && (
              <div
                style={{
                  padding: '6px 12px',
                  color: 'var(--color-text-muted)',
                  fontSize: 'var(--font-size-badge)',
                  textAlign: 'center',
                }}
              >
                显示 {triggers.length} / 总 {totalCount}
              </div>
            )}
          </>
        )}
      </div>
    </div>
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
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

type TriggerRowProps = {
  trigger: RepricingTrigger & { ticker: string }
  onClick: () => void
}

function TriggerRow({ trigger, onClick }: TriggerRowProps) {
  const color = TRIGGER_COLOR_TOKEN[trigger.triggerType]
  const label = TRIGGER_SHORT_LABELS[trigger.triggerType]
  const evidence = summarizeEvidence(trigger)

  return (
    <tr
      onClick={onClick}
      style={{ cursor: 'pointer', borderBottom: '1px solid var(--color-border)' }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLTableRowElement).style.background = 'var(--color-bg-secondary)'
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
        {trigger.ticker}
      </td>
      <td style={tdStyle}>
        <span
          data-trigger-type={trigger.triggerType}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '1px 5px',
            borderRadius: '4px',
            background: `color-mix(in srgb, ${color} 16%, transparent)`,
            color,
            fontSize: 'var(--font-size-badge)',
          }}
        >
          {label}
        </span>
      </td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>
        {trigger.detectedDate}
      </td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>
        {trigger.confidence.toFixed(2)}
      </td>
      <td style={{ ...tdStyle, color: 'var(--color-text-secondary)' }}>{evidence}</td>
    </tr>
  )
}
