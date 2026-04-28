import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/lib/api/client'
import { useCockpitStore } from '@/store/cockpitStore'
import { getCockpitDecision, type CockpitDecisionData, type GetCockpitDecisionOverrides } from '../lib/api/cockpitDecisionApi'
import { EarningsRiskDot } from '../components/EarningsRiskDot'
import { AiTradePlanSection } from '../components/AiTradePlanSection'
import { AiContradictionsSection } from '../components/AiContradictionsSection'
import { calcDaysUntil } from '../lib/utils/dates'

// ── helpers ──────────────────────────────────────────────────────────────────

function fmt2(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPct(n: number): string {
  return `${n.toFixed(2)}%`
}

// ── sub-components ────────────────────────────────────────────────────────────

const rowStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  gap: '8px',
  fontSize: 'var(--font-size-body)',
  padding: '2px 0',
}

const labelStyle: React.CSSProperties = {
  color: 'var(--color-text-secondary)',
}

const valueStyle: React.CSSProperties = {
  color: 'var(--color-text-primary)',
  fontVariantNumeric: 'tabular-nums',
}

function DecisionCard({ data }: { data: CockpitDecisionData }) {
  const daysUntil = calcDaysUntil(data.earningsDate)
  return (
    <div style={{ flex: '1 1 180px', minWidth: 0 }}>
      <div style={rowStyle}>
        <span style={labelStyle}>Entry</span>
        <span style={valueStyle}>{fmt2(data.entryPrice)}</span>
      </div>
      <div style={rowStyle}>
        <span style={labelStyle}>Stop</span>
        <span style={valueStyle}>{fmt2(data.stopPrice)}</span>
      </div>
      <div style={rowStyle}>
        <span style={labelStyle}>Target 2R</span>
        <span style={valueStyle}>{fmt2(data.target2r)}</span>
      </div>
      <div style={rowStyle}>
        <span style={labelStyle}>Target 3R</span>
        <span style={valueStyle}>{fmt2(data.target3r)}</span>
      </div>
      <div style={rowStyle}>
        <span style={labelStyle}>Risk/share</span>
        <span style={valueStyle}>${fmt2(data.riskPerShare)}</span>
      </div>
      <div style={rowStyle}>
        <span style={labelStyle}>Suggested</span>
        <span style={valueStyle}>{data.suggestedShares} shares</span>
      </div>
      <div style={rowStyle}>
        <span style={labelStyle}>Position $</span>
        <span style={valueStyle}>${data.positionValue.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
      </div>
      <div style={rowStyle}>
        <span style={labelStyle}>Account Risk</span>
        <span style={valueStyle}>{fmtPct(data.accountRiskPct)}</span>
      </div>
      {data.earningsRisk && (
        <div style={rowStyle}>
          <span style={labelStyle}>Earnings</span>
          <span style={{ ...valueStyle, display: 'flex', alignItems: 'center', gap: '4px' }}>
            <EarningsRiskDot value={data.earningsRisk} daysUntil={daysUntil} />
            {data.earningsRisk}
            {daysUntil != null && data.earningsRisk !== 'DANGER' && (
              <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-caption)' }}>
                (D-{daysUntil})
              </span>
            )}
          </span>
        </div>
      )}
      <div
        style={{
          ...rowStyle,
          marginTop: '4px',
          paddingTop: '4px',
          borderTop: '1px solid var(--color-border)',
        }}
      >
        <span style={{ ...labelStyle, fontSize: 'var(--font-size-caption)' }}>
          deterministicHash
        </span>
        <span
          style={{
            color: 'var(--color-text-muted)',
            fontSize: 'var(--font-size-caption)',
            fontFamily: 'monospace',
          }}
        >
          {data.deterministicHash.slice(0, 8)}…
        </span>
      </div>
    </div>
  )
}

type OverrideFormProps = {
  inputValues: { entryOverride: string; stopOverride: string; riskPctOverride: string }
  effectiveRiskPct?: number
  regimeCap?: number
  userSettingCap?: number
  riskPctOverride?: number
  onInputChange: (field: keyof GetCockpitDecisionOverrides, value: string) => void
  onRecompute: () => void
}

function OverrideForm({
  inputValues,
  effectiveRiskPct,
  regimeCap,
  userSettingCap,
  riskPctOverride,
  onInputChange,
  onRecompute,
}: OverrideFormProps) {
  const inputFieldStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '3px',
    marginBottom: '8px',
  }

  const overrideVal = riskPctOverride != null ? `${riskPctOverride}` : '—'

  return (
    <div style={{ flex: '1 1 160px', minWidth: 0 }}>
      <div style={inputFieldStyle}>
        <Label style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }}>
          Entry override
        </Label>
        <Input
          type="number"
          step="any"
          placeholder="—"
          value={inputValues.entryOverride}
          onChange={(e) => onInputChange('entryOverride', e.target.value)}
          style={{ height: '28px' }}
        />
      </div>

      <div style={inputFieldStyle}>
        <Label style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }}>
          Stop override
        </Label>
        <Input
          type="number"
          step="any"
          placeholder="—"
          value={inputValues.stopOverride}
          onChange={(e) => onInputChange('stopOverride', e.target.value)}
          style={{ height: '28px' }}
        />
      </div>

      <div style={inputFieldStyle}>
        <Label style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }}>
          Risk% override
        </Label>
        <Input
          type="number"
          step="any"
          placeholder="—"
          value={inputValues.riskPctOverride}
          onChange={(e) => onInputChange('riskPctOverride', e.target.value)}
          style={{ height: '28px' }}
        />
      </div>

      {effectiveRiskPct != null && (
        <div style={{ marginBottom: '8px' }}>
          <div style={{ ...rowStyle, fontWeight: 'var(--font-weight-medium)' }}>
            <span style={labelStyle}>Effective Risk%</span>
            <span style={valueStyle}>{fmtPct(effectiveRiskPct)}</span>
          </div>
          <p
            style={{
              fontSize: 'var(--font-size-caption)',
              color: 'var(--color-text-muted)',
              marginTop: '2px',
            }}
          >
            = min(regime {regimeCap ?? '—'}, user {userSettingCap ?? '—'}, override {overrideVal})
          </p>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
        <Button
          variant="outline"
          size="sm"
          type="button"
          onClick={onRecompute}
          style={{ width: '100%' }}
        >
          ↻ Recompute
        </Button>
        <Button
          variant="outline"
          size="sm"
          type="button"
          disabled
          title="F206 上线后启用"
          style={{ width: '100%', color: 'var(--color-text-disabled, var(--color-text-muted))' }}
        >
          📋 Save as PendingOrder
        </Button>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
      <div style={{ flex: '1 1 180px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} style={{ height: '20px', width: '100%' }} />
        ))}
      </div>
      <div style={{ flex: '1 1 160px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} style={{ height: '32px', width: '100%' }} />
        ))}
      </div>
    </div>
  )
}

// ── main widget ───────────────────────────────────────────────────────────────

export function DecisionPanelWidget() {
  const ticker = useCockpitStore((s) => s.selectedTicker)

  const [inputValues, setInputValues] = useState({
    entryOverride: '',
    stopOverride: '',
    riskPctOverride: '',
  })
  const [queryOverrides, setQueryOverrides] = useState<GetCockpitDecisionOverrides>({})
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  const handleOverrideChange = (field: keyof GetCockpitDecisionOverrides, value: string) => {
    setInputValues((prev) => ({ ...prev, [field]: value }))
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      const num = value === '' ? undefined : parseFloat(value)
      setQueryOverrides((prev) => {
        const next = { ...prev }
        if (num == null || isNaN(num)) {
          delete next[field]
        } else {
          next[field] = num
        }
        return next
      })
    }, 500)
  }

  const decisionQuery = useQuery({
    queryKey: ['cockpit-decision', ticker, queryOverrides],
    queryFn: () => getCockpitDecision(ticker!, queryOverrides),
    enabled: ticker != null,
    staleTime: 30 * 1000,
    retry: false,
  })

  const handleRecompute = () => {
    decisionQuery.refetch()
  }

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    padding: '12px',
    gap: '10px',
    overflow: 'auto',
    fontSize: 'var(--font-size-body)',
    color: 'var(--color-text-primary)',
  }

  // ── empty state ─────────────────────────────────────────────────────────────
  if (!ticker) {
    return (
      <div style={{ ...containerStyle, alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--color-text-secondary)', textAlign: 'center' }}>
          请在 Setup Monitor 或 Chart 选择一只股票
        </p>
      </div>
    )
  }

  const data = decisionQuery.data
  const err = decisionQuery.error
  const is404 = err instanceof ApiError && err.status === 404
  const is422 = err instanceof ApiError && err.status === 422

  const headerTitle = data
    ? `Decision · ${data.ticker} · ${data.setupType} · ${data.setupQuality}`
    : `Decision · ${ticker}`

  const overrideFormProps = {
    inputValues,
    effectiveRiskPct: data?.effectiveRiskPct,
    regimeCap: data?.regimeCap,
    userSettingCap: data?.userSettingCap,
    riskPctOverride: queryOverrides.riskPctOverride,
    onInputChange: handleOverrideChange,
    onRecompute: handleRecompute,
  }

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div
        style={{
          fontSize: 'var(--font-size-body)',
          fontWeight: 'var(--font-weight-medium)',
          color: 'var(--color-text-primary)',
          borderBottom: '1px solid var(--color-border)',
          paddingBottom: '6px',
        }}
      >
        {headerTitle}
      </div>

      {/* Body */}
      {decisionQuery.isLoading ? (
        <SkeletonCard />
      ) : is422 ? (
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 180px' }}>
            <p style={{ color: 'var(--color-signal-danger)', fontSize: 'var(--font-size-body)' }}>
              entry 必须大于 stop
            </p>
          </div>
          <OverrideForm {...overrideFormProps} />
        </div>
      ) : is404 ? (
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 180px' }}>
            <p style={{ color: 'var(--color-text-secondary)' }}>
              无 setup 数据，可手动 override entry/stop
            </p>
          </div>
          <OverrideForm {...overrideFormProps} />
        </div>
      ) : decisionQuery.isError ? (
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 180px' }}>
            <p style={{ color: 'var(--color-text-secondary)' }}>加载失败，请稍后重试</p>
          </div>
          <OverrideForm {...overrideFormProps} />
        </div>
      ) : data ? (
        <>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <DecisionCard data={data} />
            <OverrideForm {...overrideFormProps} />
          </div>
          <div
            data-testid="ai-plan-divider"
            style={{ borderTop: '1px solid var(--color-border)', paddingTop: '8px', marginTop: '4px' }}
          >
            <AiTradePlanSection decision={data} />
          </div>
          <div
            data-testid="ai-contradictions-divider"
            style={{ borderTop: '1px solid var(--color-border)', paddingTop: '8px', marginTop: '4px' }}
          >
            <AiContradictionsSection decision={data} />
          </div>
        </>
      ) : null}
    </div>
  )
}
