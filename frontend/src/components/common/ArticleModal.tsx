import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import DOMPurify from 'dompurify'
import { X, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useQuery } from '@tanstack/react-query'
import { articleKey } from '@/lib/news-persist'
import { stripHtml } from '@/components/news/newsSummaryUtils'
import { translateArticle } from '@/lib/api/translateArticle'
import { useReadArticlesStore } from '@/store/useReadArticlesStore'
import type { NewsArticle } from '@/types/news'

type Props = {
  article: NewsArticle | null
  onClose: () => void
  onSelectTicker?: (ticker: string) => void
}

export function ArticleModal({ article, onClose, onSelectTicker }: Props) {
  const closeBtnRef = useRef<HTMLButtonElement | null>(null)
  const prevFocusRef = useRef<HTMLElement | null>(null)
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
  }, [article?.url, article?.publishedAt, markAsRead])

  useEffect(() => {
    if (!article) return
    prevFocusRef.current = document.activeElement as HTMLElement | null
    closeBtnRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
      prevFocusRef.current?.focus?.()
    }
  }, [article, onClose])

  if (!article) return null

  const displayTitle = data?.output.titleZh ?? article.title ?? 'Untitled'

  const cleanHtml = DOMPurify.sanitize(article.contentHtml || '', {
    FORBID_TAGS: ['style', 'script', 'iframe', 'object', 'embed'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick'],
  })

  const meta = [article.site, article.author, formatDateTime(article.publishedAt)]
    .filter(Boolean)
    .join(' · ')

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={article.title || 'Article'}
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative"
        style={{
          background: 'var(--color-background, #fff)',
          color: 'var(--color-text-primary)',
          borderRadius: 'var(--radius-card, 12px)',
          width: 'min(800px, 100%)',
          maxHeight: '85vh',
          overflow: 'auto',
          padding: '24px',
          boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
        }}
      >
        <button
          ref={closeBtnRef}
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full hover:bg-muted"
          style={{ border: '1px solid var(--color-border)' }}
        >
          <X size={16} />
        </button>

        <h2 className="pr-10 text-lg font-semibold">{displayTitle}</h2>

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
          <div
            className="mt-1 text-xs"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            翻译失败，显示原文
          </div>
        )}
        {data?.meta.cacheHit && (
          <div
            className="mt-1 text-xs"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            已缓存
          </div>
        )}

        {meta && (
          <p
            className="mt-1 text-xs"
            style={{ color: 'var(--color-text-secondary)' }}
          >
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
              // eslint-disable-next-line react/no-array-index-key
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
    </div>,
    document.body,
  )
}

function formatDateTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}
