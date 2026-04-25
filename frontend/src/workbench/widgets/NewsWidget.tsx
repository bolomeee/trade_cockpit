import { RefreshCw } from 'lucide-react'
import { useNewsArticles } from '@/hooks/useNewsArticles'
import { articleKey } from '@/lib/news-persist'
import { useReadArticlesStore } from '@/store/useReadArticlesStore'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { NewsArticle } from '@/types/news'

const MAX_TICKER_BADGES = 5

export type NewsWidgetProps = {
  onOpenArticle?: (article: NewsArticle) => void
  onSelectTicker?: (ticker: string) => void
}

export function NewsWidget({ onOpenArticle, onSelectTicker }: NewsWidgetProps = {}) {
  const { data, isLoading, isError, refresh, isRefreshing } = useNewsArticles()

  if (isLoading) {
    return (
      <div className="flex h-full flex-col gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} style={{ height: 32 }} />
        ))}
      </div>
    )
  }

  if (isError) return <ErrorState onRetry={refresh} />
  if (!data || data.length === 0) return <EmptyState title="No news yet" />

  return (
    <div className="h-full overflow-y-auto">
      <Table className="table-fixed text-[11px] [&_th]:h-5 [&_th]:py-1 [&_th]:px-2 [&_th]:text-left [&_td]:py-[3px] [&_td]:px-2">
        <TableHeader className="sticky top-0 z-10 bg-card">
          <TableRow>
            <TableHead className="w-[100px]">Date</TableHead>
            <TableHead>Title</TableHead>
            <TableHead className="w-[280px]">
              <div className="flex items-center justify-between">
                <span>Tickers</span>
                <button
                  type="button"
                  onClick={refresh}
                  disabled={isRefreshing}
                  title="Refresh news"
                  className="rounded p-0.5 text-blue-500 transition-colors hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-30"
                >
                  <RefreshCw
                    size={13}
                    className={isRefreshing ? 'animate-spin' : ''}
                  />
                </button>
              </div>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((article, i) => (
            <NewsRow
              key={buildKey(article, i)}
              article={article}
              onOpen={onOpenArticle}
              onSelectTicker={onSelectTicker}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function buildKey(a: NewsArticle, fallback: number): string {
  return a.url ?? `${a.publishedAt}-${a.title}-${fallback}`
}

function NewsRow({
  article,
  onOpen,
  onSelectTicker,
}: {
  article: NewsArticle
  onOpen?: (a: NewsArticle) => void
  onSelectTicker?: (ticker: string) => void
}) {
  const isRead = useReadArticlesStore((s) => s.isRead(articleKey(article)))
  const visibleTickers = article.symbols.slice(0, MAX_TICKER_BADGES)
  const hiddenCount = Math.max(0, article.symbols.length - MAX_TICKER_BADGES)
  const clickable = !!onOpen

  return (
    <TableRow
      onClick={clickable ? () => onOpen?.(article) : undefined}
      className={`${clickable ? 'cursor-pointer' : 'cursor-default'}${isRead ? ' opacity-50' : ''}`}
    >
      <TableCell
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {formatRelativeTime(article.publishedAt)}
      </TableCell>
      <TableCell
        className="truncate"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {article.title || 'Untitled'}
      </TableCell>
      <TableCell>
        {visibleTickers.length === 0 ? (
          <span
            className="text-xs"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            —
          </span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {visibleTickers.map((t) => (
              <TickerChip key={t} ticker={t} onSelect={onSelectTicker} />
            ))}
            {hiddenCount > 0 && (
              <span
                className="rounded px-1.5 py-[1px] text-[10px]"
                style={{
                  color: 'var(--color-text-secondary)',
                  background: 'var(--color-surface-muted, transparent)',
                }}
              >
                +{hiddenCount}
              </span>
            )}
          </div>
        )}
      </TableCell>
    </TableRow>
  )
}

function TickerChip({
  ticker,
  onSelect,
}: {
  ticker: string
  onSelect?: (t: string) => void
}) {
  const clickable = !!onSelect
  const base =
    'rounded px-1.5 py-[1px] text-[10px] font-medium'
  if (!clickable) {
    return (
      <span
        className={base}
        style={{
          color: 'var(--color-text-secondary)',
          background: 'var(--color-surface-muted, rgba(127,127,127,0.12))',
        }}
      >
        {ticker}
      </span>
    )
  }
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        onSelect?.(ticker)
      }}
      className={`${base} cursor-pointer hover:bg-muted`}
      style={{
        color: 'var(--color-text-primary)',
        background: 'var(--color-surface-muted, rgba(127,127,127,0.12))',
        border: '1px solid var(--color-border)',
      }}
    >
      {ticker}
    </button>
  )
}

const SECOND = 1000
const MINUTE = 60 * SECOND
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

function formatRelativeTime(iso: string): string {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return iso
  const diff = Date.now() - t
  if (diff < MINUTE) return 'just now'
  if (diff < HOUR) return `${Math.floor(diff / MINUTE)}m ago`
  if (diff < DAY) return `${Math.floor(diff / HOUR)}h ago`
  const days = Math.floor(diff / DAY)
  if (days < 7) return `${days}d ago`
  return new Date(t).toISOString().slice(0, 10)
}
