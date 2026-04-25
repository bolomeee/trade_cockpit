import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/api/client'
import {
  getCockpitRegime,
  type CockpitRegimeData,
  type RegimeLabel,
  type IndexState,
  type SectorState,
  type RegimeIndex,
  type RegimeSector,
  type RegimeSubscores,
} from '../lib/api/cockpitRegimeApi'

// ── constants ────────────────────────────────────────────────────────────────

const SUBSCORE_MAX = {
  spyTrend: 25,
  qqqTrend: 20,
  iwmBreadth: 15,
  sectorParticipation: 20,
  riskAppetite: 10,
  volatilityStress: 10,
} as const

const SUBSCORE_LABELS: Record<keyof typeof SUBSCORE_MAX, string> = {
  spyTrend: 'SPY Trend',
  qqqTrend: 'QQQ Trend',
  iwmBreadth: 'IWM Breadth',
  sectorParticipation: 'Sector Part.',
  riskAppetite: 'Risk Appetite',
  volatilityStress: 'Volatility',
}

// ── color helpers ─────────────────────────────────────────────────────────────

function regimeColor(regime: RegimeLabel): string {
  const map: Record<RegimeLabel, string> = {
    RISK_ON: 'var(--color-regime-risk-on)',
    CONSTRUCTIVE: 'var(--color-regime-constructive)',
    NEUTRAL: 'var(--color-regime-neutral)',
    DEFENSIVE: 'var(--color-regime-defensive)',
    RISK_OFF: 'var(--color-regime-risk-off)',
  }
  return map[regime]
}

function indexStateColor(state: IndexState): string {
  const map: Record<IndexState, string> = {
    Bullish: 'var(--color-regime-risk-on)',
    Leading: 'var(--color-regime-risk-on)',
    Constructive: 'var(--color-regime-constructive)',
    Neutral: 'var(--color-regime-neutral)',
    Weak: 'var(--color-regime-defensive)',
    Defensive: 'var(--color-regime-risk-off)',
  }
  return map[state]
}

function sectorStateColor(state: SectorState): string {
  const map: Record<SectorState, string> = {
    Strong: 'var(--color-regime-risk-on)',
    Constructive: 'var(--color-regime-constructive)',
    Neutral: 'var(--color-regime-neutral)',
    Weak: 'var(--color-regime-defensive)',
    Defensive: 'var(--color-regime-risk-off)',
  }
  return map[state]
}

function subscoreBarColor(pct: number): string {
  if (pct >= 0.8) return 'var(--color-regime-risk-on)'
  if (pct >= 0.6) return 'var(--color-regime-constructive)'
  if (pct >= 0.4) return 'var(--color-log-warn)'
  if (pct >= 0.2) return 'var(--color-regime-defensive)'
  return 'var(--color-regime-risk-off)'
}

// ── score hero ────────────────────────────────────────────────────────────────

function ScoreHero({ data }: { data: CockpitRegimeData }) {
  const color = regimeColor(data.regime)
  return (
    <div style={{ padding: '8px 0 12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
        <span
          style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: '4px',
            backgroundColor: color,
            color: 'var(--color-text-on-dark)',
            fontSize: 'var(--font-size-label)',
            fontWeight: 600,
            letterSpacing: '0.04em',
          }}
        >
          {data.regime}
        </span>
        <span style={{ fontSize: 'var(--font-size-body)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
          {data.marketScore} / 100
        </span>
      </div>
      <div style={{ fontSize: 'var(--font-size-body)', color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
        <div>Allowed Exposure: <span style={{ color: 'var(--color-text-primary)' }}>{data.allowedExposurePct.toFixed(1)}%</span></div>
        <div>Single Trade Risk: <span style={{ color: 'var(--color-text-primary)' }}>{data.singleTradeRiskPct.toFixed(1)}%</span></div>
      </div>
    </div>
  )
}

// ── subscores grid ─────────────────────────────────────────────────────────────

function SubscoreCard({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? value / max : 0
  return (
    <div
      style={{
        padding: '6px 8px',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        minHeight: '52px',
      }}
    >
      <div style={{ fontSize: 'var(--font-size-label)', color: 'var(--color-text-secondary)', marginBottom: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {label}
      </div>
      <div style={{ fontSize: 'var(--font-size-body)', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '4px' }}>
        {value} / {max}
      </div>
      <div style={{ height: '4px', borderRadius: '2px', backgroundColor: 'var(--color-muted)' }}>
        <div
          style={{
            height: '100%',
            borderRadius: '2px',
            width: `${Math.round(pct * 100)}%`,
            backgroundColor: subscoreBarColor(pct),
          }}
        />
      </div>
    </div>
  )
}

function SubscoresGrid({ subscores }: { subscores: RegimeSubscores }) {
  const keys = Object.keys(SUBSCORE_MAX) as Array<keyof typeof SUBSCORE_MAX>
  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ fontSize: 'var(--font-size-label)', color: 'var(--color-text-secondary)', marginBottom: '6px' }}>Subscores</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
        {keys.map((key) => (
          <SubscoreCard
            key={key}
            label={SUBSCORE_LABELS[key]}
            value={subscores[key]}
            max={SUBSCORE_MAX[key]}
          />
        ))}
      </div>
    </div>
  )
}

// ── indices card ───────────────────────────────────────────────────────────────

function IndexRow({ idx }: { idx: RegimeIndex }) {
  const changePctStr = idx.changePct >= 0 ? `+${idx.changePct.toFixed(2)}%` : `${idx.changePct.toFixed(2)}%`
  const changePctColor = idx.changePct >= 0 ? 'var(--color-change-positive)' : 'var(--color-change-negative)'
  const rsTrendArrow = idx.rsTrend === 'up' ? '↑' : idx.rsTrend === 'down' ? '↓' : '→'
  const stateColor = indexStateColor(idx.state)

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 0',
        fontSize: 'var(--font-size-body)',
        borderBottom: '1px solid var(--color-border-subtle)',
      }}
    >
      <span style={{ fontWeight: 600, width: '36px', flexShrink: 0 }}>{idx.symbol}</span>
      <span style={{ width: '60px', flexShrink: 0 }}>${idx.close.toFixed(2)}</span>
      <span style={{ color: changePctColor, width: '56px', flexShrink: 0 }}>{changePctStr}</span>
      <span style={{ color: 'var(--color-text-secondary)', flexShrink: 0 }}>
        50MA{idx.aboveMa50 ? '✓' : '✗'}
      </span>
      <span style={{ color: 'var(--color-text-secondary)', flexShrink: 0 }}>
        200MA{idx.aboveMa200 ? '✓' : '✗'}
      </span>
      <span style={{ color: 'var(--color-text-secondary)', flexShrink: 0 }}>{rsTrendArrow}</span>
      <span style={{ color: stateColor, fontWeight: 500, marginLeft: 'auto' }}>{idx.state}</span>
    </div>
  )
}

function IndicesCard({ indices }: { indices: RegimeIndex[] }) {
  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ fontSize: 'var(--font-size-label)', color: 'var(--color-text-secondary)', marginBottom: '6px' }}>Indices</div>
      <div>
        {indices.map((idx) => (
          <IndexRow key={idx.symbol} idx={idx} />
        ))}
      </div>
    </div>
  )
}

// ── sector heatmap ────────────────────────────────────────────────────────────

function SectorCell({ sector }: { sector: RegimeSector }) {
  const [hovered, setHovered] = useState(false)
  const bgColor = sectorStateColor(sector.state)
  const closeStr = sector.close != null ? `$${sector.close.toFixed(2)}` : '—'
  const changePctStr =
    sector.changePct != null
      ? sector.changePct >= 0
        ? `+${sector.changePct.toFixed(2)}%`
        : `${sector.changePct.toFixed(2)}%`
      : '—'

  return (
    <div
      style={{ position: 'relative' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        style={{
          padding: '4px 2px',
          borderRadius: '4px',
          backgroundColor: `color-mix(in srgb, ${bgColor} 25%, var(--color-card))`,
          border: `1px solid color-mix(in srgb, ${bgColor} 40%, transparent)`,
          textAlign: 'center',
          cursor: 'default',
          minHeight: '36px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div style={{ fontSize: 'var(--font-size-label)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
          {sector.symbol}
        </div>
        <div
          data-testid={`sector-${sector.symbol}-close`}
          style={{ fontSize: '10px', color: 'var(--color-text-secondary)' }}
        >
          {closeStr}
        </div>
      </div>
      {hovered && sector.close != null && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: 'var(--color-primary)',
            color: 'var(--color-text-on-dark)',
            padding: '4px 8px',
            borderRadius: '4px',
            fontSize: '11px',
            whiteSpace: 'nowrap',
            zIndex: 10,
            pointerEvents: 'none',
          }}
        >
          {closeStr}, {changePctStr}
        </div>
      )}
    </div>
  )
}

const SECTOR_ORDER = ['XLK', 'XLY', 'XLF', 'XLI', 'XLE', 'XLV', 'XLC', 'XLP', 'XLU', 'XLB', 'XLRE'] as const

function SectorHeatmap({ sectors }: { sectors: RegimeSector[] }) {
  const bySymbol = Object.fromEntries(sectors.map((s) => [s.symbol, s]))
  return (
    <div>
      <div style={{ fontSize: 'var(--font-size-label)', color: 'var(--color-text-secondary)', marginBottom: '6px' }}>Sector Heatmap</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px' }}>
        {SECTOR_ORDER.map((sym) => {
          const sector = bySymbol[sym]
          if (!sector) return null
          return <SectorCell key={sym} sector={sector} />
        })}
        {/* empty placeholder for 12th cell */}
        <div />
      </div>
    </div>
  )
}

// ── state variants ────────────────────────────────────────────────────────────

function RegimeSkeleton() {
  return (
    <div style={{ padding: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <Skeleton data-testid="skeleton" style={{ height: '96px', borderRadius: '6px' }} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} data-testid="skeleton" style={{ height: '52px', borderRadius: '6px' }} />
        ))}
      </div>
      {Array.from({ length: 3 }).map((_, i) => (
        <Skeleton key={i} data-testid="skeleton" style={{ height: '28px', borderRadius: '4px' }} />
      ))}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px' }}>
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton key={i} data-testid="skeleton" style={{ height: '36px', borderRadius: '4px' }} />
        ))}
      </div>
    </div>
  )
}

function RegimeEmptyState() {
  return (
    <div
      style={{
        padding: '24px 16px',
        textAlign: 'center',
        color: 'var(--color-text-secondary)',
        fontSize: 'var(--font-size-body)',
      }}
    >
      首日 regime 计算中，明日开盘后可见
    </div>
  )
}

function RegimeError({ onRetry }: { onRetry: () => void }) {
  return (
    <div style={{ padding: '24px 16px', textAlign: 'center' }}>
      <Button
        variant="outline"
        size="sm"
        onClick={onRetry}
        style={{ color: 'var(--color-error)', borderColor: 'var(--color-error)' }}
      >
        加载失败，重试
      </Button>
    </div>
  )
}

// ── shell ─────────────────────────────────────────────────────────────────────

export function MarketRegimeWidget() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['cockpit', 'regime'],
    queryFn: getCockpitRegime,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  if (isLoading) return <RegimeSkeleton />

  if (error) {
    const isNotFound = error instanceof ApiError && error.status === 404
    if (isNotFound) return <RegimeEmptyState />
    return <RegimeError onRetry={() => refetch()} />
  }

  if (!data) return null

  return (
    <div style={{ padding: '8px 12px', overflowY: 'auto', height: '100%' }}>
      <div style={{ fontSize: 'var(--font-size-label)', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
        Market Regime
      </div>
      <ScoreHero data={data} />
      <SubscoresGrid subscores={data.subscores} />
      <IndicesCard indices={data.indices} />
      <SectorHeatmap sectors={data.sectors} />
    </div>
  )
}
