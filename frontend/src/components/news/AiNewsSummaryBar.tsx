import { useState, useEffect, useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { callAiTask } from '@/cockpit/lib/api/aiApi'
import { ApiError } from '@/lib/api/client'
import { useNewsArticles } from '@/hooks/useNewsArticles'
import { useAppStore } from '@/store/useAppStore'
import { RefreshCw, Loader2 } from 'lucide-react'
import {
  articlesHash,
  buildSummarizerArticles,
  type NewsArticleItem,
} from './newsSummaryUtils'

// ── Internal types (mirrors backend news_summarizer.py 1:1) ───────────────────

type Sentiment = 'positive' | 'neutral' | 'negative'

type NewsSummarizerInput = {
  articles: NewsArticleItem[]
  windowDays: number
}

type NewsSummarizerOutput = {
  catalystSummary: string
  sentiment: Sentiment
  relevantTickers: string[]
  risks: string[]
}

// ── Sentiment badge styles ─────────────────────────────────────────────────────

const SENTIMENT_STYLE: Record<Sentiment, { bg: string; fg: string; label: string }> = {
  positive: {
    bg: 'color-mix(in srgb, var(--color-success) 20%, transparent)',
    fg: 'var(--color-success)',
    label: 'Positive',
  },
  neutral: {
    bg: 'color-mix(in srgb, var(--color-text-muted) 12%, transparent)',
    fg: 'var(--color-text-secondary)',
    label: 'Neutral',
  },
  negative: {
    bg: 'color-mix(in srgb, var(--color-error) 20%, transparent)',
    fg: 'var(--color-error)',
    label: 'Negative',
  },
}

// ── Shared sub-components ─────────────────────────────────────────────────────

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

function SectionHeader({
  cacheBadge,
  onClose,
  closeTestId,
  onRefresh,
  isRefreshing,
}: {
  cacheBadge?: string
  onClose: () => void
  closeTestId: string
  onRefresh?: () => void
  isRefreshing?: boolean
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
      <span
        style={{
          fontSize: 'var(--font-size-caption)',
          fontWeight: 'var(--font-weight-medium)',
          color: 'var(--color-text-primary)',
        }}
      >
        AI News Summary
      </span>
      {cacheBadge && (
        <span
          data-testid="ai-news-summary-cache-badge"
          style={{
            fontSize: 'var(--font-size-badge)',
            color: 'var(--color-text-muted)',
            marginLeft: 'auto',
          }}
        >
          {cacheBadge}
        </span>
      )}
      {onRefresh && (
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          title="重新生成"
          style={{
            background: 'none',
            border: 'none',
            cursor: isRefreshing ? 'default' : 'pointer',
            color: 'var(--color-text-muted)',
            padding: '0 2px',
            lineHeight: 1,
            display: 'flex',
            alignItems: 'center',
            opacity: isRefreshing ? 0.5 : 1,
          }}
        >
          {isRefreshing
            ? <Loader2 size={12} className="animate-spin" />
            : <RefreshCw size={12} />}
        </button>
      )}
      <CloseButton onClose={onClose} testId={closeTestId} />
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function AiNewsSummaryBar(): JSX.Element | null {
  const open = useAppStore((s) => s.aiNewsSummaryOpen)
  const setOpen = useAppStore((s) => s.setAiNewsSummaryOpen)
  const [hash, setHash] = useState<string | null>(null)
  const setSelectedSymbol = useAppStore((s) => s.setSelectedSymbol)
  const forceNoCache = useRef(false)

  const { data: articles = [] } = useNewsArticles()
  const isDisabled = articles.length === 0

  const summarizerArticles = useMemo(
    () => buildSummarizerArticles(articles),
    [articles],
  )

  useEffect(() => {
    if (!open || summarizerArticles.length === 0) return
    articlesHash(summarizerArticles).then(setHash)
  }, [open, summarizerArticles])

  const hashReady = hash !== null

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['ai', 'news_summarizer', hash ?? '__pending__'],
    queryFn: () => {
      const nc = forceNoCache.current
      return callAiTask<NewsSummarizerInput, NewsSummarizerOutput>('news_summarizer', {
        articles: summarizerArticles,
        windowDays: 5,
      }, { noCache: nc })
    },
    enabled: open && !isDisabled && hashReady,
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    retry: false,
  })

  const handleRefresh = () => {
    forceNoCache.current = true
    refetch().finally(() => { forceNoCache.current = false })
  }

  const isSpinning = isLoading || (isFetching && !data)
  const isRefreshing = isFetching && !!data
  const is409 = error instanceof ApiError && error.status === 409

  // ── State 1: closed ──────────────────────────────────────────────────────
  if (!open) return null

  // ── State 2: loading ─────────────────────────────────────────────────────
  if (isSpinning) {
    return (
      <div data-testid="ai-news-summary-loading">
        <SectionHeader onClose={() => setOpen(false)} closeTestId="ai-news-summary-loading-close" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <Skeleton
            data-testid="ai-news-summary-skeleton-summary"
            style={{ height: '64px', borderRadius: '4px' }}
          />
          <Skeleton
            data-testid="ai-news-summary-skeleton-risks"
            style={{ height: '40px', borderRadius: '4px' }}
          />
        </div>
      </div>
    )
  }

  // ── State 3: 409 guardrail violation ─────────────────────────────────────
  if (is409) {
    return (
      <div
        data-testid="ai-news-summary-guardrail-error"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 10px',
          borderRadius: '4px',
          background: 'color-mix(in srgb, var(--color-error) 15%, transparent)',
        }}
      >
        <span style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-error)' }}>
          AI 输出被拦截
        </span>
        <CloseButton onClose={() => setOpen(false)} testId="ai-news-summary-guardrail-close" />
      </div>
    )
  }

  // ── State 4: other error ─────────────────────────────────────────────────
  if (error) {
    return (
      <div
        data-testid="ai-news-summary-error"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 'var(--font-size-caption)',
          color: 'var(--color-text-secondary)',
        }}
      >
        <span>AI 暂不可用</span>
        <CloseButton onClose={() => setOpen(false)} testId="ai-news-summary-error-close" />
      </div>
    )
  }

  // ── State 5 & 6: success ─────────────────────────────────────────────────
  if (data) {
    const cacheBadge = data.meta.cacheHit ? 'Cached' : `Generated · ${data.meta.modelUsed}`
    const { catalystSummary, sentiment, relevantTickers, risks } = data.output
    const sentimentStyle = SENTIMENT_STYLE[sentiment]

    return (
      <div data-testid="ai-news-summary-result">
        <SectionHeader
          cacheBadge={cacheBadge}
          onClose={() => setOpen(false)}
          closeTestId="ai-news-summary-close"
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
        />

        <p
          data-testid="ai-news-summary-catalyst"
          style={{
            fontSize: 'var(--font-size-caption)',
            color: 'var(--color-text-primary)',
            lineHeight: 'var(--line-height-normal)',
            margin: '0 0 6px 0',
          }}
        >
          {catalystSummary}
        </p>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span
            data-testid="ai-news-summary-sentiment"
            style={{
              fontSize: 'var(--font-size-badge)',
              fontWeight: 'var(--font-weight-medium)',
              padding: '1px 6px',
              borderRadius: '2px',
              background: sentimentStyle.bg,
              color: sentimentStyle.fg,
            }}
          >
            {sentimentStyle.label}
          </span>
        </div>

        {relevantTickers.length > 0 && (
          <div
            data-testid="ai-news-summary-tickers"
            style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap', marginBottom: '6px' }}
          >
            <span
              style={{
                fontSize: 'var(--font-size-badge)',
                color: 'var(--color-text-muted)',
                marginRight: '2px',
              }}
            >
              Tickers:
            </span>
            {relevantTickers.map((ticker) => (
              <button
                key={ticker}
                type="button"
                onClick={() => setSelectedSymbol(ticker)}
                style={{
                  padding: '1px 6px',
                  borderRadius: '2px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-input-background)',
                  color: 'var(--color-text-primary)',
                  cursor: 'pointer',
                  fontSize: 'var(--font-size-badge)',
                  fontWeight: 'var(--font-weight-medium)',
                }}
              >
                {ticker}
              </button>
            ))}
          </div>
        )}

        {risks.length > 0 && (
          <div data-testid="ai-news-summary-risks">
            {risks.map((risk, i) => (
              <p
                key={i}
                style={{
                  fontSize: 'var(--font-size-caption)',
                  color: 'var(--color-text-secondary)',
                  margin: '2px 0',
                }}
              >
                · {risk}
              </p>
            ))}
          </div>
        )}
      </div>
    )
  }

  return <></>
}
