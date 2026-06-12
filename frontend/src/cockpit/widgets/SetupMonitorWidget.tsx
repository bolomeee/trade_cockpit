import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CircleX, Loader2 } from 'lucide-react'
import { useCockpitStore } from '@/store/cockpitStore'
import {
  getSetupMonitor,
  type SetupFilterValue,
  type SetupItem,
  type SetupSummary,
} from '../lib/api/setupMonitorApi'
import { STAGE_LABELS, readStageColor } from '../lib/weeklyStageTokens'
import { removeStock } from '@/lib/api/watchlist'
import { SetupTypeBadge } from '../components/SetupTypeBadge'
import { SetupQualityBadge } from '../components/SetupQualityBadge'
import { EarningsRiskDot } from '../components/EarningsRiskDot'
import { getCockpitRegime } from '../lib/api/cockpitRegimeApi'
import { AiCandidateRankerSection } from '../components/AiCandidateRankerSection'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

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
      {/* Header — title + tabs + AI ranker on a single row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '5px 10px',
          borderBottom: '1px solid var(--color-border)',
          flexShrink: 0,
          flexWrap: 'wrap',
        }}
      >
        <ToggleGroup
          type="single"
          size="sm"
          spacing={1}
          value={activeTab}
          onValueChange={(v) => v && setActiveTab(v as FilterTab)}
          aria-label="Setup filter"
        >
          {TABS.map((tab) => (
            <ToggleGroupItem
              key={tab.key}
              value={tab.key}
              aria-label={tab.key}
              className="text-xs font-normal"
            >
              {tab.label(data?.summary)}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>

        <div style={{ marginLeft: 'auto' }}>
          <AiCandidateRankerSection
            items={items}
            regime={regimeData?.regime ?? null}
            regimeScore={regimeData?.marketScore ?? null}
          />
        </div>
      </div>

      {/* Table */}
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
                <Th width="13%">Ticker</Th>
                <Th width="14%">Setup</Th>
                <Th width="5%">Q</Th>
                <Th width="10%">Entry</Th>
                <Th width="10%">Stop</Th>
                <Th width="7%">R:R</Th>
                <Th width="9%">Dist</Th>
                <Th width="5%">RS</Th>
                <Th width="6%">Vol Z</Th>
                <Th width="6%" align="center">WS</Th>
                <Th width="7%" align="center">Earn</Th>
                <Th width="8%"></Th>
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

function Th({ children, width, align = 'left' }: { children?: React.ReactNode; width: string; align?: 'left' | 'center' | 'right' }) {
  return (
    <th
      style={{
        padding: '2px 5px',
        textAlign: align,
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
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const deleteMutation = useMutation({
    mutationFn: () => removeStock(item.ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cockpit-setup-monitor'] })
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      setDialogOpen(false)
      setDeleteError(null)
    },
    onError: () => {
      setDeleteError('删除失败，请重试')
    },
  })

  return (
    <tr
      onClick={onClick}
      style={{
        cursor: 'pointer',
        borderBottom: '1px solid var(--color-border)',
        position: 'relative',
        opacity: deleteMutation.isPending ? 0.5 : 1,
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
          padding: '3px 5px',
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
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <SetupTypeBadge value={item.setupType} />
          {item.setupType === 'CAPITULATION' && item.macdDivergence === 'bullish' && (
            <span
              data-testid={`macd-plus-${item.ticker}`}
              title="bullish divergence — auxiliary evidence for CAPITULATION (not part of ready gate)"
              aria-label="bullish divergence chip"
              style={{
                color: 'var(--color-change-positive)',
                fontSize: 'var(--font-size-badge)',
                fontWeight: 'var(--font-weight-medium)',
                letterSpacing: '0.04em',
              }}
            >
              MACD+
            </span>
          )}
        </span>
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
      <td style={{ ...tdStyle, fontFamily: 'var(--font-family-numeric)' }}>
        {fmt2(item.volumeZscore)}
      </td>
      <td style={{ ...tdStyle, textAlign: 'center' }}>
        <WeeklyStageCell stage={item.weeklyStage} />
      </td>
      <td style={{ ...tdStyle, textAlign: 'center' }}>
        <EarningsRiskDot value={item.earningsRisk} />
      </td>
      <td style={{ ...tdStyle, textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
        <AlertDialog
          open={dialogOpen}
          onOpenChange={(open) => {
            setDialogOpen(open)
            if (!open) setDeleteError(null)
          }}
        >
          <AlertDialogTrigger asChild>
            <button
              type="button"
              aria-label={`删除 ${item.ticker}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '18px',
                height: '18px',
                borderRadius: '3px',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                color: 'var(--color-text-muted)',
                padding: 0,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--color-destructive, #ef4444)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--color-text-muted)'
              }}
            >
              <CircleX size={13} strokeWidth={1.5} />
            </button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>确认删除</AlertDialogTitle>
              <AlertDialogDescription>
                从 watchlist 中移除 <strong>{item.ticker}</strong>？
              </AlertDialogDescription>
            </AlertDialogHeader>
            {deleteError && (
              <div style={{ color: 'var(--color-change-negative)', fontSize: 'var(--font-size-caption)' }}>
                {deleteError}
              </div>
            )}
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleteMutation.isPending}>取消</AlertDialogCancel>
              <AlertDialogAction
                variant="destructive"
                disabled={deleteMutation.isPending}
                onClick={(e) => {
                  e.preventDefault()
                  deleteMutation.mutate()
                }}
              >
                {deleteMutation.isPending ? (
                  <>
                    <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                    删除中…
                  </>
                ) : (
                  '删除'
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </td>
    </tr>
  )
}

const tdStyle: React.CSSProperties = {
  padding: '3px 5px',
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-text-primary)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

function WeeklyStageCell({ stage }: { stage: number | null }) {
  if (stage == null || stage === 0) {
    return (
      <span
        title={stage === 0 ? STAGE_LABELS[0] : '无 Weekly Stage 数据'}
        style={{ color: 'var(--color-text-muted)' }}
      >
        —
      </span>
    )
  }
  const color = readStageColor(stage)
  const label = STAGE_LABELS[stage] ?? 'Unknown'
  return (
    <span
      data-stage={stage}
      title={label}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        fontFamily: 'var(--font-family-numeric)',
        color: 'var(--color-text-primary)',
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: color,
          display: 'inline-block',
        }}
      />
      {stage}
    </span>
  )
}
