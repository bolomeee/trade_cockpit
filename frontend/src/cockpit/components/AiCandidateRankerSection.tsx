import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { callAiTask } from '../lib/api/aiApi'
import type { RegimeLabel } from '../lib/api/cockpitRegimeApi'
import type { SetupItem, SetupType, EarningsRisk } from '../lib/api/setupMonitorApi'

// ── Types ─────────────────────────────────────────────────────────────────────

export type CandidateInput = {
  ticker: string
  setupType: SetupType
  setupQuality: 'A' | 'B' | 'C' | null
  trendScore: number
  rsPercentile: number
  distanceToEntryPct: number
  rewardRisk: number
  earningsRisk: EarningsRisk
  readySignal: boolean
}

export type CandidateRankerInput = {
  regime: RegimeLabel
  regimeScore: number
  candidates: CandidateInput[]
}

export type RankedCandidate = {
  ticker: string
  rank: 1 | 2 | 3
  reason: string
  action: 'enter' | 'watch' | 'wait'
}

export type CandidateRankerOutput = {
  topCandidates: RankedCandidate[]
}

// ── Props ─────────────────────────────────────────────────────────────────────

type Props = {
  items: SetupItem[]
  regime: RegimeLabel | null
  regimeScore: number | null
}

// ── Input builder ─────────────────────────────────────────────────────────────

function buildCandidateRankerInput(
  items: SetupItem[],
  regime: RegimeLabel,
  regimeScore: number,
): CandidateRankerInput {
  const candidates: CandidateInput[] = items.slice(0, 20).map((item) => ({
    ticker: item.ticker,
    setupType: item.setupType,
    setupQuality: item.setupQuality,
    trendScore: item.trendScore,
    rsPercentile: item.rsPercentile,
    distanceToEntryPct: item.distanceToEntryPct ?? 0,
    rewardRisk: Math.max(item.rewardRisk ?? 0, 0),
    earningsRisk: item.earningsRisk,
    readySignal: item.readySignal,
  }))
  return { regime, regimeScore, candidates }
}

// ── Action badge (inline, enter/watch/wait 三色) ───────────────────────────────

function ActionBadge({ value }: { value: 'enter' | 'watch' | 'wait' }) {
  const colorMap = {
    enter: 'var(--color-signal-breakout)',
    watch: 'var(--color-log-warn)',
    wait: 'var(--color-text-muted)',
  }
  const color = colorMap[value]
  const isFilled = value !== 'wait'
  return (
    <span
      data-testid="ai-rank-action-badge"
      style={{
        display: 'inline-block',
        padding: '1px 5px',
        borderRadius: '3px',
        fontSize: 'var(--font-size-badge)',
        fontWeight: 'var(--font-weight-medium)',
        color: isFilled ? 'var(--color-text-on-dark)' : color,
        background: isFilled ? color : 'transparent',
        border: isFilled ? 'none' : `1px solid ${color}`,
      }}
    >
      {value}
    </span>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function AiCandidateRankerSection({ items, regime, regimeScore }: Props) {
  const [open, setOpen] = useState(false)

  // inputKey: regime + front-20 tickers; filter tab change naturally shifts inputKey → new request
  const inputKey = useMemo(() => {
    const tickers = items.slice(0, 20).map((i) => i.ticker).join(',')
    return `${regime ?? ''}|${tickers}`
  }, [items, regime])

  const wasTruncated = items.length > 20

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['ai', 'candidate_ranker', inputKey],
    queryFn: () =>
      callAiTask<CandidateRankerInput, CandidateRankerOutput>(
        'candidate_ranker',
        buildCandidateRankerInput(items, regime!, regimeScore!),
      ),
    enabled: open && regime != null && regimeScore != null && items.length >= 1,
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    retry: false,
  })

  const isSpinning = isLoading || (isFetching && !data)
  const isDisabled = regime == null || regimeScore == null || items.length === 0

  return (
    <>
      {/* Trigger button — marginLeft:auto pushes it right in the flex-wrap tabs row */}
      <button
        data-testid="ai-rank-trigger"
        aria-label="AI rank top setups"
        onClick={() => setOpen((o) => !o)}
        disabled={isDisabled}
        style={{
          marginLeft: 'auto',
          padding: '4px 10px',
          borderRadius: '4px',
          border: '1px solid var(--color-border)',
          background: open ? 'var(--color-signal-breakout)' : 'var(--color-bg-secondary)',
          color: open ? 'var(--color-text-on-dark)' : 'var(--color-text-primary)',
          cursor: isDisabled ? 'default' : 'pointer',
          fontSize: 'var(--font-size-caption)',
          fontWeight: 'var(--font-weight-medium)',
          opacity: isDisabled ? 0.5 : 1,
          flexShrink: 0,
        }}
      >
        AI 排序
      </button>

      {/* Result panel — flexBasis:100% breaks onto its own row inside the flex-wrap tabs container */}
      {open && (
        <div
          data-testid="ai-rank-panel"
          style={{
            flexBasis: '100%',
            order: 999,
            paddingTop: '6px',
          }}
        >
          {isSpinning && (
            <div
              data-testid="ai-rank-skeletons"
              style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}
            >
              {[1, 2, 3].map((r) => (
                <Skeleton
                  key={r}
                  data-testid="ai-rank-skeleton"
                  style={{ height: '28px', borderRadius: '4px' }}
                />
              ))}
            </div>
          )}

          {!isSpinning && error && (
            <div
              data-testid="ai-rank-error"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: 'var(--font-size-caption)',
                color: 'var(--color-text-secondary)',
              }}
            >
              <span>AI 排序暂不可用</span>
              <button
                data-testid="ai-rank-error-close"
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
          )}

          {!isSpinning && !error && data && (
            <div>
              {/* Top bar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  marginBottom: '4px',
                }}
              >
                <span
                  style={{
                    fontSize: 'var(--font-size-caption)',
                    fontWeight: 'var(--font-weight-medium)',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  AI 排序 · top 3
                </span>

                {wasTruncated && (
                  <span
                    data-testid="ai-rank-truncated"
                    style={{
                      fontSize: 'var(--font-size-badge)',
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    Top 20 / {items.length}
                  </span>
                )}

                <span
                  data-testid="ai-rank-cache-badge"
                  style={{
                    fontSize: 'var(--font-size-badge)',
                    color: 'var(--color-text-muted)',
                    marginLeft: 'auto',
                  }}
                >
                  {data.meta.cacheHit ? 'Cached' : `Generated · ${data.meta.modelUsed}`}
                </span>

                <button
                  data-testid="ai-rank-close"
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

              {/* Ranked cards */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                {data.output.topCandidates.map((c) => (
                  <div
                    key={c.ticker}
                    data-testid={`ai-rank-card-${c.rank}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 6px',
                      background: 'var(--color-bg-secondary)',
                      borderRadius: '4px',
                      fontSize: 'var(--font-size-caption)',
                    }}
                  >
                    <span
                      data-testid={`ai-rank-num-${c.rank}`}
                      style={{
                        color: 'var(--color-text-muted)',
                        fontFamily: 'var(--font-family-numeric)',
                        minWidth: '16px',
                      }}
                    >
                      #{c.rank}
                    </span>
                    <span
                      data-testid={`ai-rank-ticker-${c.rank}`}
                      style={{
                        fontWeight: 'var(--font-weight-medium)',
                        color: 'var(--color-text-primary)',
                        minWidth: '44px',
                      }}
                    >
                      {c.ticker}
                    </span>
                    <ActionBadge value={c.action} />
                    <span
                      data-testid={`ai-rank-reason-${c.rank}`}
                      style={{
                        color: 'var(--color-text-secondary)',
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {c.reason}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}
