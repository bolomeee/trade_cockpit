import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { callAiTask } from '../lib/api/aiApi'
import { ApiError } from '@/lib/api/client'
import type { CockpitDecisionData } from '../lib/api/cockpitDecisionApi'
import type { SetupType, EarningsRisk } from '../lib/api/setupMonitorApi'

// ── Types ─────────────────────────────────────────────────────────────────────

export type TradePlanInput = {
  ticker: string
  setupType: SetupType
  setupQuality: 'A' | 'B' | 'C' | null
  entry: number
  stop: number
  target2r: number
  target3r: number
  size: number
  rewardRisk: number
  accountRiskPct: number
  earningsRisk: EarningsRisk
  deterministicHash: string
}

export type TradePlanOutput = {
  memo: string
  management: string[]
  entry: number
  stop: number
  size: number
}

// ── Input builder ─────────────────────────────────────────────────────────────

function buildTradePlanInput(decision: CockpitDecisionData): TradePlanInput {
  return {
    ticker: decision.ticker,
    setupType: decision.setupType,
    setupQuality: decision.setupQuality,
    entry: decision.entryPrice,        // rename: entryPrice → entry
    stop: decision.stopPrice,          // rename: stopPrice → stop
    target2r: decision.target2r,
    target3r: decision.target3r,
    size: decision.suggestedShares,    // rename: suggestedShares → size
    rewardRisk: decision.rewardRisk,
    accountRiskPct: decision.accountRiskPct,
    earningsRisk: decision.earningsRisk,
    deterministicHash: decision.deterministicHash,
  }
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

// ── Main component ────────────────────────────────────────────────────────────

type Props = {
  decision: CockpitDecisionData
}

export function AiTradePlanSection({ decision }: Props) {
  const [open, setOpen] = useState(false)

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['ai', 'trade_plan', decision.ticker, decision.deterministicHash],
    queryFn: () =>
      callAiTask<TradePlanInput, TradePlanOutput>(
        'trade_plan',
        buildTradePlanInput(decision),
      ),
    enabled: open,
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
        data-testid="ai-plan-trigger"
        aria-label="Generate AI trade plan"
        onClick={() => setOpen(true)}
        style={{
          padding: '6px 12px',
          borderRadius: '4px',
          border: '1px solid var(--color-border)',
          background: 'var(--color-input-background)',
          color: 'var(--color-text-primary)',
          cursor: 'pointer',
          fontSize: 'var(--font-size-caption)',
          fontWeight: 'var(--font-weight-medium)',
        }}
      >
        Generate AI Plan
      </button>
    )
  }

  // ── State 2: loading ─────────────────────────────────────────────────────
  if (isSpinning) {
    return (
      <div data-testid="ai-plan-loading">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
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
            AI Trade Plan
          </span>
          <CloseButton onClose={() => setOpen(false)} testId="ai-plan-loading-close" />
        </div>
        <div
          data-testid="ai-plan-skeletons"
          style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}
        >
          <Skeleton data-testid="ai-plan-skeleton-memo" style={{ height: '60px', borderRadius: '4px' }} />
          <Skeleton data-testid="ai-plan-skeleton-mgmt" style={{ height: '80px', borderRadius: '4px' }} />
        </div>
      </div>
    )
  }

  // ── State 3: 409 guardrail violation ────────────────────────────────────
  if (is409) {
    return (
      <div
        data-testid="ai-plan-guardrail-error"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 10px',
          borderRadius: '4px',
          background: `color-mix(in srgb, var(--color-error) 15%, transparent)`,
        }}
      >
        <span
          data-testid="ai-plan-guardrail-message"
          style={{
            fontSize: 'var(--font-size-caption)',
            color: 'var(--color-error)',
          }}
        >
          AI 输出被拦截 — 数字不匹配
        </span>
        <CloseButton onClose={() => setOpen(false)} testId="ai-plan-guardrail-close" />
      </div>
    )
  }

  // ── State 4: other error ─────────────────────────────────────────────────
  if (error) {
    return (
      <div
        data-testid="ai-plan-error"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 'var(--font-size-caption)',
          color: 'var(--color-text-secondary)',
        }}
      >
        <span>AI 暂不可用</span>
        <CloseButton onClose={() => setOpen(false)} testId="ai-plan-error-close" />
      </div>
    )
  }

  // ── State 5: success ─────────────────────────────────────────────────────
  if (data) {
    const cacheBadge = data.meta.cacheHit ? 'Cached' : `Generated · ${data.meta.modelUsed}`

    return (
      <div data-testid="ai-plan-result">
        {/* Top bar */}
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
            AI Trade Plan
          </span>

          <span
            data-testid="ai-plan-guardrail-passed"
            style={{
              fontSize: 'var(--font-size-badge)',
              color: 'var(--color-success)',
              fontWeight: 'var(--font-weight-medium)',
            }}
          >
            ✓ Guardrail passed
          </span>

          <span
            data-testid="ai-plan-cache-badge"
            style={{
              fontSize: 'var(--font-size-badge)',
              color: 'var(--color-text-muted)',
              marginLeft: 'auto',
            }}
          >
            {cacheBadge}
          </span>

          <button
            data-testid="ai-plan-close"
            onClick={() => setOpen(false)}
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
        </div>

        {/* Memo */}
        <p
          data-testid="ai-plan-memo"
          style={{
            fontSize: 'var(--font-size-caption)',
            color: 'var(--color-text-primary)',
            lineHeight: 'var(--line-height-normal)',
            margin: '6px 0',
            whiteSpace: 'pre-wrap',
          }}
        >
          {data.output.memo}
        </p>

        {/* Management list */}
        <ol
          data-testid="ai-plan-management-list"
          style={{
            margin: 0,
            paddingLeft: '20px',
            fontSize: 'var(--font-size-caption)',
            color: 'var(--color-text-primary)',
          }}
        >
          {data.output.management.map((rule, i) => (
            <li
              key={i}
              data-testid={`ai-plan-management-item-${i}`}
              style={{ padding: '2px 0' }}
            >
              {rule}
            </li>
          ))}
        </ol>
      </div>
    )
  }

  // ── State 6: defensive (open but no data/error/loading — shouldn't happen) ──
  return null
}
