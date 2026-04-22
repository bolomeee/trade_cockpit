import { useNewsArticles } from '@/hooks/useNewsArticles'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import type { NewsArticle } from '@/types/news'

const MAX_TICKER_BADGES = 3

export function NewsWidget() {
  const { data, isLoading, isError, refetch } = useNewsArticles()

  if (isLoading) {
    return (
      <div className="flex h-full flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} style={{ height: 64 }} />
        ))}
      </div>
    )
  }

  if (isError) return <ErrorState onRetry={() => refetch()} />
  if (!data || data.length === 0) return <EmptyState title="No news yet" />

  return (
    <div className="h-full overflow-y-auto">
      <ul className="flex flex-col gap-1">
        {data.map((article, i) => (
          <NewsCard key={buildKey(article, i)} article={article} />
        ))}
      </ul>
    </div>
  )
}

function buildKey(a: NewsArticle, fallback: number): string {
  return a.url ?? `${a.publishedAt}-${a.title}-${fallback}`
}

function NewsCard({ article }: { article: NewsArticle }) {
  const clickable = !!article.url

  const handleClick = () => {
    if (article.url) {
      window.open(article.url, '_blank', 'noopener,noreferrer')
    }
  }

  const visibleTickers = article.symbols.slice(0, MAX_TICKER_BADGES)
  const hiddenCount = Math.max(0, article.symbols.length - MAX_TICKER_BADGES)

  return (
    <li
      onClick={clickable ? handleClick : undefined}
      className={
        'flex gap-3 rounded-md p-2 ' +
        (clickable ? 'cursor-pointer hover:bg-muted/50' : 'cursor-default')
      }
    >
      {article.imageUrl && (
        <img
          src={article.imageUrl}
          alt=""
          loading="lazy"
          className="h-12 w-12 shrink-0 rounded object-cover"
          onError={(e) => {
            ;(e.currentTarget as HTMLImageElement).style.display = 'none'
          }}
        />
      )}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p
          className="line-clamp-1 text-sm font-medium"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {article.title || 'Untitled'}
        </p>
        <p
          className="text-xs"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {[article.site, formatRelativeTime(article.publishedAt)]
            .filter(Boolean)
            .join(' · ')}
        </p>
        {visibleTickers.length > 0 && (
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
      </div>
    </li>
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
