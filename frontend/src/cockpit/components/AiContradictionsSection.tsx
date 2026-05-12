import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { callAiTask } from '../lib/api/aiApi'
import { ApiError } from '@/lib/api/client'
import { getSetupMonitor, type SetupItem } from '../lib/api/setupMonitorApi'
import { getCockpitRegime, type CockpitRegimeData, type RegimeLabel } from '../lib/api/cockpitRegimeApi'
import { calcDaysUntil } from '../lib/utils/dates'
import type { CockpitDecisionData } from '../lib/api/cockpitDecisionApi'
import type { SetupType, EarningsRisk } from '../lib/api/setupMonitorApi'

// ── Types ─────────────────────────────────────────────────────────────────────

type Severity = 'LOW' | 'MEDIUM' | 'HIGH'

type ContradictionType =
  | 'earnings_risk'
  | 'reward_risk'
  | 'trend_quality'
  | 'extension'
  | 'regime_misfit'
  | 'volume'
  | 'other'

type ContradictionItem = {
  type: ContradictionType
  severity: Severity
  text: string
}

type ContradictionDetectorInput = {
  ticker: string
  setupType: SetupType
  setupQuality: 'A' | 'B' | 'C' | null
  trendScore: number
  rsPercentile: number
  entry: number
  stop: number
  target2r: number
  rewardRisk: number
  accountRiskPct: number
  earningsRisk: EarningsRisk | null
  daysToEarnings: number | null
  regime: RegimeLabel
  regimeScore: number
  readySignal: boolean
}

type ContradictionDetectorOutput = {
  contradictions: ContradictionItem[]
  recommendation: string
}

// ── Input builder ─────────────────────────────────────────────────────────────

function buildContradictionInput(
  decision: CockpitDecisionData,
  setupItem: SetupItem,
  regime: CockpitRegimeData,
): ContradictionDetectorInput {
  return {
    ticker: decision.ticker,
    setupType: decision.setupType,
    setupQuality: decision.setupQuality,
    trendScore: setupItem.trendScore,
    rsPercentile: setupItem.rsPercentile,
    entry: decision.entryPrice,
    stop: decision.stopPrice,
    target2r: decision.target2r,
    rewardRisk: decision.rewardRisk,
    accountRiskPct: decision.accountRiskPct,
    earningsRisk: decision.earningsRisk,
    daysToEarnings: calcDaysUntil(decision.earningsDate),
    regime: regime.regime,
    regimeScore: regime.marketScore,
    readySignal: setupItem.readySignal,
  }
}

// ── Severity tag styles ────────────────────────────────────────────────────────
// Note: --color-signal-warning absent in tokens.css (verified step 1); using --color-log-warn (#f59e0b)

const SEVERITY_TAG: Record<Severity, { bg: string; fg: string; prefix: string }> = {
  HIGH: {
    bg: 'color-mix(in srgb, var(--color-error) 20%, transparent)',
    fg: 'var(--color-error)',
    prefix: '⚠',
  },
  MEDIUM: {
    bg: 'color-mix(in srgb, var(--color-log-warn) 20%, transparent)',
    fg: 'var(--color-log-warn)',
    prefix: '⚠',
  },
  LOW: {
    bg: 'color-mix(in srgb, var(--color-text-muted) 12%, transparent)',
    fg: 'var(--color-text-secondary)',
    prefix: '·',
  },
}

// ── Shared close button ───────────────────────────────────────────────────────

function CloseButton({ onClose, testId }: { onClose: () => void; testId: string }) {
  return (
    <button
      data-testid={testId}
      onClick={onClose}
      style={{
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        color: 'var(--color-text-muted)',
        fontSize: 'var(--font-size-caption)',
        padding: '0 2px',
        lineHeight: 1,
      }}
    >
      ✕
    </button>
  )
}

// ── Section header ────────────────────────────────────────────────────────────

function SectionHeader({
  cacheBadge,
  onClose,
  closeTestId,
}: {
  cacheBadge?: string
  onClose: () => void
  closeTestId: string
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '6px',
      }}
    >
      <span
        style={{
          fontSize: 'var(--font-size-caption)',
          fontWeight: 'var(--font-weight-medium)',
          color: 'var(--color-text-primary)',
        }}
      >
        AI Contradictions
      </span>
      {cacheBadge && (
        <span
          data-testid="ai-contradictions-cache-badge"
          style={{
            fontSize: 'var(--font-size-badge)',
            color: 'var(--color-text-muted)',
            marginLeft: 'auto',
          }}
        >
          {cacheBadge}
        </span>
      )}
      <CloseButton onClose={onClose} testId={closeTestId} />
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

type Props = {
  decision: CockpitDecisionData
}

export function AiContradictionsSection({ decision }: Props) {
  const [open, setOpen] = useState(false)

  // Subscribe to setup/regime caches (enabled:open → deduped with SetupMonitorWidget/MarketRegimeWidget)
  // enabled:false still returns cached data reactively; enabled:true also fetches if stale/missing
  const { data: setupData } = useQuery({
    queryKey: ['cockpit-setup-monitor', 'all'],
    queryFn: () => getSetupMonitor([]),
    enabled: open,
    staleTime: 5 * 60 * 1000,
  })
  const { data: regimeData } = useQuery({
    queryKey: ['cockpit-regime'],
    queryFn: getCockpitRegime,
    enabled: open,
    staleTime: 5 * 60 * 1000,
  })

  const setupItem = setupData?.items.find((i) => i.ticker === decision.ticker)
  const isDisabled = !setupItem || !regimeData

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['ai', 'contradiction_detector', decision.ticker, decision.deterministicHash],
    queryFn: () =>
      callAiTask<ContradictionDetectorInput, ContradictionDetectorOutput>(
        'contradiction_detector',
        buildContradictionInput(decision, setupItem!, regimeData!),
      ),
    enabled: open && !isDisabled,
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    retry: false,
  })

  const isSpinning = isLoading || (isFetching && !data)
  const is409 = error instanceof ApiError && error.status === 409

  // ── State 1: closed ──────────────────────────────────────────────────────
  if (!open) {
    return (
      <button
        data-testid="ai-contradictions-trigger"
        aria-label="Generate AI Contradictions"
        disabled={isDisabled}
        title={isDisabled ? '需 Setup Monitor 数据' : undefined}
        onClick={() => setOpen(true)}
        style={{
          padding: '6px 12px',
          borderRadius: '4px',
          border: '1px solid var(--color-border)',
          background: 'var(--color-input-background)',
          color: isDisabled ? 'var(--color-text-muted)' : 'var(--color-text-primary)',
          cursor: isDisabled ? 'not-allowed' : 'pointer',
          fontSize: 'var(--font-size-caption)',
          fontWeight: 'var(--font-weight-medium)',
          opacity: isDisabled ? 0.6 : 1,
        }}
      >
        Generate AI Contradictions
      </button>
    )
  }

  // ── State 2: loading ─────────────────────────────────────────────────────
  if (isSpinning) {
    return (
      <div data-testid="ai-contradictions-loading">
        <SectionHeader onClose={() => setOpen(false)} closeTestId="ai-contradictions-loading-close" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <Skeleton data-testid="ai-contradictions-skeleton-list" style={{ height: '48px', borderRadius: '4px' }} />
          <Skeleton data-testid="ai-contradictions-skeleton-rec" style={{ height: '20px', borderRadius: '4px' }} />
        </div>
      </div>
    )
  }

  // ── State 3: 409 guardrail violation ─────────────────────────────────────
  if (is409) {
    return (
      <div
        data-testid="ai-contradictions-guardrail-error"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 10px',
          borderRadius: '4px',
          background: 'color-mix(in srgb, var(--color-error) 15%, transparent)',
        }}
      >
        <span
          style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-error)' }}
        >
          AI 输出被拦截
        </span>
        <CloseButton onClose={() => setOpen(false)} testId="ai-contradictions-guardrail-close" />
      </div>
    )
  }

  // ── State 4: other error ─────────────────────────────────────────────────
  if (error) {
    return (
      <div
        data-testid="ai-contradictions-error"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 'var(--font-size-caption)',
          color: 'var(--color-text-secondary)',
        }}
      >
        <span>AI 暂不可用</span>
        <CloseButton onClose={() => setOpen(false)} testId="ai-contradictions-error-close" />
      </div>
    )
  }

  // ── State 5 & 6: success ─────────────────────────────────────────────────
  if (data) {
    const cacheBadge = data.meta.cacheHit ? 'Cached' : `Generated · ${data.meta.modelUsed}`
    const { contradictions, recommendation } = data.output

    return (
      <div data-testid="ai-contradictions-result">
        <SectionHeader
          cacheBadge={cacheBadge}
          onClose={() => setOpen(false)}
          closeTestId="ai-contradictions-close"
        />

        {contradictions.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '6px' }}>
            {contradictions.map((item, i) => {
              const style = SEVERITY_TAG[item.severity]
              return (
                <div
                  key={i}
                  data-testid={`ai-contradictions-item-${i}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '6px',
                  }}
                >
                  <span
                    style={{
                      fontSize: 'var(--font-size-caption)',
                      color: 'var(--color-text-primary)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <span style={{ color: style.fg }}>{style.prefix}</span>
                    {item.text}
                  </span>
                  <span
                    data-testid={`ai-contradictions-severity-${i}`}
                    style={{
                      flexShrink: 0,
                      fontSize: 'var(--font-size-badge)',
                      fontWeight: 'var(--font-weight-medium)',
                      padding: '0 6px',
                      height: '16px',
                      lineHeight: '16px',
                      borderRadius: '2px',
                      background: style.bg,
                      color: style.fg,
                    }}
                  >
                    {item.severity}
                  </span>
                </div>
              )
            })}
          </div>
        )}

        <p
          data-testid="ai-contradictions-recommendation"
          style={{
            fontSize: 'var(--font-size-caption)',
            color: 'var(--color-text-primary)',
            lineHeight: 'var(--line-height-normal)',
            margin: 0,
          }}
        >
          Recommendation: {recommendation}
        </p>
      </div>
    )
  }

  return null
}
