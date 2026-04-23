import { useNewsArticles } from '@/hooks/useNewsArticles'
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

const MAX_TICKER_BADGES = 3

export function NewsWidget() {
  const { data, isLoading, isError, refetch } = useNewsArticles()

  if (isLoading) {
    return (
      <div className="flex h-full flex-col gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} style={{ height: 32 }} />
        ))}
      </div>
    )
  }

  if (isError) return <ErrorState onRetry={() => refetch()} />
  if (!data || data.length === 0) return <EmptyState title="No news yet" />

  return (
    <div className="h-full overflow-y-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[120px]">Date</TableHead>
            <TableHead className="w-[140px]">Site</TableHead>
            <TableHead>Title</TableHead>
            <TableHead className="w-[180px]">Tickers</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((article, i) => (
            <NewsRow key={buildKey(article, i)} article={article} />
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function buildKey(a: NewsArticle, fallback: number): string {
  return a.url ?? `${a.publishedAt}-${a.title}-${fallback}`
}

function NewsRow({ article }: { article: NewsArticle }) {
  const visibleTickers = article.symbols.slice(0, MAX_TICKER_BADGES)
  const hiddenCount = Math.max(0, article.symbols.length - MAX_TICKER_BADGES)

  return (
    <TableRow className="cursor-default">
      <TableCell
        className="text-xs"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {formatRelativeTime(article.publishedAt)}
      </TableCell>
      <TableCell
        className="text-xs"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {article.site || '—'}
      </TableCell>
      <TableCell
        className="line-clamp-1 max-w-0 text-sm font-medium"
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
              <TickerChip key={t} ticker={t} />
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

function TickerChip({ ticker }: { ticker: string }) {
  return (
    <span
      className="rounded px-1.5 py-[1px] text-[10px] font-medium"
      style={{
        color: 'var(--color-text-secondary)',
        background: 'var(--color-surface-muted, rgba(127,127,127,0.12))',
      }}
    >
      {ticker}
    </span>
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
