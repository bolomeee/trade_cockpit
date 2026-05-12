import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { RotateCw } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { ButtonGroup } from '@/components/ui/button-group'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
  const [isRefreshing, setIsRefreshing] = useState(false)
  const queryClient = useQueryClient()

  async function handleRefreshSetup() {
    setIsRefreshing(true)
    try {
      await fetch('/api/admin/refresh-setup', { method: 'POST' })
      await queryClient.invalidateQueries({ queryKey: ['cockpit-setup-monitor'] })
    } finally {
      setIsRefreshing(false)
    }
  }

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
      <ButtonGroup>
        <Button
          data-testid="ai-rank-trigger"
          aria-label="AI rank top setups"
          aria-expanded={open}
          variant="outline"
          size="sm"
          className="text-xs font-normal"
          onClick={() => setOpen((o) => !o)}
          disabled={isDisabled}
        >
          AI 排序
        </Button>
        <Button
          aria-label="Refresh setup scan"
          variant="outline"
          size="sm"
          className="text-xs font-normal"
          onClick={handleRefreshSetup}
          disabled={isRefreshing}
        >
          <RotateCw
            size={11}
            style={isRefreshing ? { animation: 'spin 1s linear infinite' } : undefined}
          />
        </Button>
      </ButtonGroup>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="ai-rank-panel" className="max-w-md" aria-describedby={undefined}>
          <DialogHeader>
            <DialogTitle className="text-sm font-medium">
              AI 排序 · Top 3
              {wasTruncated && (
                <span
                  data-testid="ai-rank-truncated"
                  className="ml-2 text-xs font-normal text-muted-foreground"
                >
                  (Top 20 / {items.length})
                </span>
              )}
            </DialogTitle>
          </DialogHeader>

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
            <p
              data-testid="ai-rank-error"
              style={{
                fontSize: 'var(--font-size-caption)',
                color: 'var(--color-text-secondary)',
              }}
            >
              AI 排序暂不可用
            </p>
          )}

          {!isSpinning && !error && data && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {data.output.topCandidates.map((c) => (
                <div
                  key={c.ticker}
                  data-testid={`ai-rank-card-${c.rank}`}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '8px',
                    padding: '8px 10px',
                    background: 'var(--color-bg-secondary)',
                    borderRadius: '6px',
                    fontSize: 'var(--font-size-caption)',
                  }}
                >
                  <span
                    data-testid={`ai-rank-num-${c.rank}`}
                    style={{
                      color: 'var(--color-text-muted)',
                      fontFamily: 'var(--font-family-numeric)',
                      minWidth: '18px',
                      paddingTop: '1px',
                    }}
                  >
                    #{c.rank}
                  </span>
                  <span
                    data-testid={`ai-rank-ticker-${c.rank}`}
                    style={{
                      fontWeight: 'var(--font-weight-medium)',
                      color: 'var(--color-text-primary)',
                      minWidth: '48px',
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
                      lineHeight: 1.4,
                      whiteSpace: 'normal',
                    }}
                  >
                    {c.reason}
                  </span>
                </div>
              ))}

              <p
                data-testid="ai-rank-cache-badge"
                style={{
                  fontSize: 'var(--font-size-badge)',
                  color: 'var(--color-text-muted)',
                  textAlign: 'right',
                  marginTop: '2px',
                }}
              >
                {data.meta.cacheHit ? 'Cached' : `Generated · ${data.meta.modelUsed}`}
              </p>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
