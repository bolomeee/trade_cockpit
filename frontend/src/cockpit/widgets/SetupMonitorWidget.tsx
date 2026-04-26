import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useCockpitStore } from '@/store/cockpitStore'
import {
  getSetupMonitor,
  type SetupFilterValue,
  type SetupItem,
  type SetupSummary,
} from '../lib/api/setupMonitorApi'
import { SetupTypeBadge } from '../components/SetupTypeBadge'
import { SetupQualityBadge } from '../components/SetupQualityBadge'
import { EarningsRiskDot } from '../components/EarningsRiskDot'
import { AiSetupExplainerPopover } from '../components/AiSetupExplainerPopover'
import { getCockpitRegime } from '../lib/api/cockpitRegimeApi'
import { AiCandidateRankerSection } from '../components/AiCandidateRankerSection'

type FilterTab = 'all' | SetupFilterValue

type TabDef = {
  key: FilterTab
  label: (s: SetupSummary | undefined) => string
  filters: SetupFilterValue[]
}

const TABS: TabDef[] = [
  { key: 'all', label: (s) => `All ${s?.total ?? ''}`, filters: [] },
  { key: 'ready', label: (s) => `Ready ${s?.ready ?? ''}`, filters: ['ready'] },
  { key: 'near', label: (s) => `Near ${s?.near ?? ''}`, filters: ['near'] },
  { key: 'extended', label: (s) => `Extended ${s?.extended ?? ''}`, filters: ['extended'] },
  { key: 'broken', label: (s) => `Broken ${s?.broken ?? ''}`, filters: ['broken'] },
]

const ACTION_ORDER: Record<string, number> = {
  enter: 0,
  watch: 1,
  wait: 2,
  reduce: 4,
  exit: 5,
}

function actionOrder(a: string | null) {
  return a ? (ACTION_ORDER[a] ?? 3) : 3
}

export function SetupMonitorWidget() {
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const setSelectedTicker = useCockpitStore((s) => s.setSelectedTicker)

  const currentTab = TABS.find((t) => t.key === activeTab)!

  const { data, isLoading, isError } = useQuery({
    queryKey: ['cockpit-setup-monitor', activeTab],
    queryFn: () => getSetupMonitor(currentTab.filters),
    staleTime: 5 * 60 * 1000,
  })

  const { data: regimeData } = useQuery({
    queryKey: ['cockpit-regime'],
    queryFn: getCockpitRegime,
    staleTime: 5 * 60 * 1000,
  })

  const items = data
    ? [...data.items].sort((a, b) => actionOrder(a.suggestedAction) - actionOrder(b.suggestedAction))
    : []

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
          padding: '8px 12px 0',
          fontWeight: 'var(--font-weight-medium)',
          color: 'var(--color-text-primary)',
          fontSize: 'var(--font-size-body)',
          flexShrink: 0,
        }}
      >
        Setup Monitor
      </div>

      {/* Filter Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '2px',
          padding: '6px 12px',
          borderBottom: '1px solid var(--color-border)',
          flexShrink: 0,
          flexWrap: 'wrap',
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '2px 8px',
              borderRadius: '4px',
              border: 'none',
              cursor: 'pointer',
              fontSize: 'var(--font-size-caption)',
              background:
                activeTab === tab.key
                  ? 'var(--color-signal-breakout)'
                  : 'var(--color-bg-secondary)',
              color:
                activeTab === tab.key
                  ? 'var(--color-text-on-dark)'
                  : 'var(--color-text-secondary)',
              fontWeight:
                activeTab === tab.key
                  ? 'var(--font-weight-medium)'
                  : 'var(--font-weight-normal)',
            }}
          >
            {tab.label(data?.summary)}
          </button>
        ))}
        <AiCandidateRankerSection
          items={items}
          regime={regimeData?.regime ?? null}
          regimeScore={regimeData?.marketScore ?? null}
        />
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto' }}>
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
          <div
            style={{
              padding: '16px 12px',
              color: 'var(--color-change-negative)',
              textAlign: 'center',
            }}
          >
            Failed to load setup data
          </div>
        )}

        {!isLoading && !isError && items.length === 0 && (
          <div
            style={{
              padding: '16px 12px',
              color: 'var(--color-text-muted)',
              textAlign: 'center',
            }}
          >
            No setups
          </div>
        )}

        {!isLoading && !isError && items.length > 0 && (
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              tableLayout: 'fixed',
            }}
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
                <Th width="16%">Setup</Th>
                <Th width="5%">Q</Th>
                <Th width="11%">Entry</Th>
                <Th width="11%">Stop</Th>
                <Th width="8%">R:R</Th>
                <Th width="10%">Dist</Th>
                <Th width="8%">RS</Th>
                <Th width="8%">Earn</Th>
                <Th width="5%">?</Th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <SetupRow
                  key={item.ticker}
                  item={item}
                  onClick={() => setSelectedTicker(item.ticker)}
                />
              ))}
            </tbody>
          </table>
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

function fmt2(v: number | null | undefined) {
  return v != null ? v.toFixed(2) : '—'
}

function SetupRow({ item, onClick }: { item: SetupItem; onClick: () => void }) {
  const dist = item.distanceToEntryPct ?? null
  const distStr =
    dist != null ? `${dist >= 0 ? '+' : ''}${dist.toFixed(2)}%` : '—'

  return (
    <tr
      onClick={onClick}
      style={{
        cursor: 'pointer',
        borderBottom: '1px solid var(--color-border)',
        position: 'relative',
      }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLTableRowElement).style.background =
          'var(--color-bg-secondary)'
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLTableRowElement).style.background = 'transparent'
      }}
    >
      {/* Ready signal: left blue bar via box-shadow on first cell */}
      <td
        style={{
          padding: '5px 6px',
          fontFamily: 'var(--font-family-numeric)',
          fontWeight: 'var(--font-weight-medium)',
          color: 'var(--color-text-primary)',
          boxShadow: item.readySignal
            ? 'inset 3px 0 0 var(--color-signal-breakout)'
            : undefined,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={item.stockName}
      >
        {item.ticker}
      </td>
      <td style={tdStyle}>
        <SetupTypeBadge value={item.setupType} />
      </td>
      <td style={tdStyle}>
        <SetupQualityBadge value={item.setupQuality} />
      </td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>
        {fmt2(item.entryPrice)}
      </td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>
        {fmt2(item.stopPrice)}
      </td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>
        {item.rewardRisk != null ? item.rewardRisk.toFixed(1) : '—'}
      </td>
      <td
        style={{
          ...tdStyle,
          fontFamily: 'var(--font-family-numeric)',
          color:
            dist != null && Math.abs(dist) < 1
              ? 'var(--color-change-positive)'
              : 'var(--color-text-primary)',
        }}
      >
        {distStr}
      </td>
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>
        {item.rsPercentile}
      </td>
      <td style={tdStyle}>
        <EarningsRiskDot value={item.earningsRisk} />
      </td>
      <td style={{ ...tdStyle, textAlign: 'right' }}>
        {(item.setupType === 'BREAKOUT' || item.setupType === 'PULLBACK' || item.setupType === 'RECLAIM') &&
          item.entryPrice > 0 &&
          item.stopPrice > 0 && (
            <AiSetupExplainerPopover
              ticker={item.ticker}
              setupType={item.setupType}
              trendScore={item.trendScore}
              rsPercentile={item.rsPercentile}
              entryPrice={item.entryPrice}
              stopPrice={item.stopPrice}
            />
          )}
      </td>
    </tr>
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
