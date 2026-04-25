import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { callAiTask } from '../lib/api/aiApi'

// ── Types (defined here; each AI task owns its own types per arch decision) ───

export type SetupExplainerInput = {
  ticker: string
  trend: 'up' | 'down' | 'sideways'
  rs: number
  setup: 'pullback' | 'breakout' | 'reversal' | 'range' | 'gap_fill'
  risk: { entry: number; stop: number }
}

export type SetupExplainerOutput = {
  label: string
  quality: 'A' | 'B' | 'C' | 'D'
  whyWatch: string
  mainRisks: string[]
}

// ── Props ─────────────────────────────────────────────────────────────────────

type Props = {
  ticker: string
  setupType: 'BREAKOUT' | 'PULLBACK' | 'RECLAIM'
  trendScore: number
  rsPercentile: number
  entryPrice: number
  stopPrice: number
}

// ── Input builder ─────────────────────────────────────────────────────────────

function buildSetupExplainerInput(p: Props): SetupExplainerInput {
  const setup = (
    p.setupType === 'BREAKOUT' ? 'breakout' :
    p.setupType === 'PULLBACK' ? 'pullback' :
    'reversal'
  ) as const
  // trend_score is a 0-5 MA-alignment ladder (backend setup_service._compute_trend_score):
  //   4-5 → bullish stack (close>MA10>MA21>MA50…) → 'up'
  //   2-3 → partial alignment → 'sideways'
  //   0-1 → MA inverted → 'down'
  const trend =
    p.trendScore >= 4 ? 'up' :
    p.trendScore <= 1 ? 'down' :
    'sideways'
  return {
    ticker: p.ticker,
    trend,
    rs: p.rsPercentile,
    setup,
    risk: { entry: p.entryPrice, stop: p.stopPrice },
  }
}

// ── Quality badge (inline, supports A/B/C/D) ──────────────────────────────────

const QUALITY_COLOR: Record<'A' | 'B' | 'C' | 'D', string> = {
  A: 'var(--color-regime-risk-on)',
  B: 'var(--color-regime-constructive)',
  C: 'var(--color-log-warn)',
  D: 'var(--color-regime-defensive)',
}

function QualityBadge({ value }: { value: 'A' | 'B' | 'C' | 'D' }) {
  return (
    <span
      data-testid="ai-explainer-quality"
      style={{
        display: 'inline-block',
        padding: '1px 6px',
        borderRadius: '4px',
        backgroundColor: QUALITY_COLOR[value],
        color: 'var(--color-text-on-dark)',
        fontSize: 'var(--font-size-badge)',
        fontWeight: 'var(--font-weight-medium)',
        lineHeight: 1.4,
        verticalAlign: 'middle',
      }}
    >
      {value}
    </span>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function AiSetupExplainerPopover(props: Props) {
  const [open, setOpen] = useState(false)

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['ai', 'setup_explainer', props.ticker, props.setupType],
    queryFn: () =>
      callAiTask<SetupExplainerInput, SetupExplainerOutput>(
        'setup_explainer',
        buildSetupExplainerInput(props),
      ),
    enabled: open,
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    retry: false,
  })

  const isSpinning = isLoading || (isFetching && !data)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          aria-label={`Explain ${props.ticker} ${props.setupType} setup`}
          onClick={(e) => e.stopPropagation()}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--color-text-muted)',
            fontSize: 'var(--font-size-caption)',
            padding: '2px 4px',
            lineHeight: 1,
          }}
        >
          ?
        </button>
      </PopoverTrigger>

      <PopoverContent align="end" sideOffset={4} style={{ width: 280 }}>
        {isSpinning && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <Skeleton data-testid="ai-explainer-skeleton" style={{ height: '18px', borderRadius: '4px' }} />
            <Skeleton data-testid="ai-explainer-skeleton" style={{ height: '48px', borderRadius: '4px' }} />
            <Skeleton data-testid="ai-explainer-skeleton" style={{ height: '32px', borderRadius: '4px' }} />
          </div>
        )}

        {!isSpinning && error && (
          <div
            data-testid="ai-explainer-error"
            style={{
              fontSize: 'var(--font-size-caption)',
              color: 'var(--color-text-secondary)',
            }}
          >
            AI 暂不可用
          </div>
        )}

        {!isSpinning && !error && data && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* Label + Quality badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span
                data-testid="ai-explainer-label"
                style={{
                  fontSize: 'var(--font-size-caption)',
                  fontWeight: 'var(--font-weight-medium)',
                  color: 'var(--color-text-primary)',
                }}
              >
                {data.output.label}
              </span>
              <QualityBadge value={data.output.quality} />
            </div>

            {/* whyWatch */}
            <p
              data-testid="ai-explainer-why-watch"
              style={{
                margin: 0,
                fontSize: 'var(--font-size-caption)',
                color: 'var(--color-text-secondary)',
                lineHeight: 1.5,
              }}
            >
              {data.output.whyWatch}
            </p>

            {/* mainRisks */}
            <ul
              data-testid="ai-explainer-risks"
              style={{
                margin: 0,
                paddingLeft: '14px',
                fontSize: 'var(--font-size-caption)',
                color: 'var(--color-text-secondary)',
                lineHeight: 1.5,
              }}
            >
              {data.output.mainRisks.map((risk, i) => (
                <li key={i}>{risk}</li>
              ))}
            </ul>
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}
