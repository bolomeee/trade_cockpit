import { useEffect } from 'react'
import DOMPurify from 'dompurify'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useQuery } from '@tanstack/react-query'
import { articleKey } from '@/lib/news-persist'
import { stripHtml } from '@/components/news/newsSummaryUtils'
import { translateArticle } from '@/lib/api/translateArticle'
import { useReadArticlesStore } from '@/store/useReadArticlesStore'
import { EmptyState } from '@/components/common/EmptyState'
import type { NewsArticle } from '@/types/news'

export type ArticleDetailWidgetProps = {
  article?: NewsArticle | null
  onSelectTicker?: (ticker: string) => void
}

export function ArticleDetailWidget({
  article = null,
  onSelectTicker,
}: ArticleDetailWidgetProps = {}) {
  const markAsRead = useReadArticlesStore((s) => s.markAsRead)

  const contentText = article ? stripHtml(article.contentHtml ?? '') : ''

  const { data, isLoading, isError } = useQuery({
    queryKey: ['translate-article', article ? articleKey(article) : null],
    queryFn: () =>
      translateArticle({
        title: article!.title,
        contentText,
      }),
    enabled: !!article && contentText.length > 0,
    staleTime: Infinity,
    gcTime: 5 * 60 * 1000,
    retry: 1,
  })

  useEffect(() => {
    if (isError) toast.error('文章翻译失败，已显示原文')
  }, [isError])

  useEffect(() => {
    if (article) markAsRead(articleKey(article))
    // Key on identity fields only; the article object is a fresh ref each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [article?.url, article?.publishedAt, markAsRead])

  if (!article) {
    return <EmptyState title="点击左侧新闻查看详情" />
  }

  const displayTitle = data?.output.titleZh ?? article.title ?? 'Untitled'

  const cleanHtml = DOMPurify.sanitize(article.contentHtml || '', {
    FORBID_TAGS: ['style', 'script', 'iframe', 'object', 'embed'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick'],
  })

  const meta = [article.site, article.author, formatDateTime(article.publishedAt)]
    .filter(Boolean)
    .join(' · ')

  return (
    <div role="article" className="h-full">
      <h2 className="text-base font-semibold">{displayTitle}</h2>

      {/* Translation status bar */}
      {isLoading && (
        <div
          className="mt-1 flex items-center gap-1 text-xs"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          <Loader2 size={12} className="animate-spin" />
          <span>正在翻译...</span>
        </div>
      )}
      {isError && (
        <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          翻译失败，显示原文
        </div>
      )}
      {data?.meta.cacheHit && (
        <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          已缓存
        </div>
      )}

      {meta && (
        <p className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {meta}
        </p>
      )}

      {article.symbols.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {article.symbols.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => onSelectTicker?.(t)}
              className="rounded px-2 py-[2px] text-xs font-medium hover:bg-muted"
              style={{
                color: 'var(--color-text-primary)',
                background: 'var(--color-surface-muted, rgba(127,127,127,0.12))',
                border: '1px solid var(--color-border)',
              }}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {data?.output.contentZh ? (
        <div
          className="article-content mt-4 text-sm leading-relaxed"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {data.output.contentZh.split('\n\n').map((para, i) => (
            <p key={i} className={i > 0 ? 'mt-3' : undefined}>
              {para}
            </p>
          ))}
        </div>
      ) : (
        <div
          className="article-content mt-4 text-sm leading-relaxed"
          style={{ color: 'var(--color-text-primary)' }}
          dangerouslySetInnerHTML={{ __html: cleanHtml }}
        />
      )}
    </div>
  )
}

function formatDateTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}
