import type { NewsArticle } from '@/types/news'

export type NewsArticleItem = {
  title: string
  contentText: string
  tickers: string[]
  publishedAt: string
}

export function stripHtml(html: string): string {
  if (!html) return ''
  const doc = new DOMParser().parseFromString(html, 'text/html')
  return (doc.body.textContent ?? '').trim().slice(0, 2000)
}

export function sortByPublishedDesc(articles: NewsArticle[]): NewsArticle[] {
  return [...articles].sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
}

export async function articlesHash(items: NewsArticleItem[]): Promise<string> {
  const sorted = [...items]
    .map((a) => ({ t: a.title, p: a.publishedAt }))
    .sort((a, b) => a.p.localeCompare(b.p) || a.t.localeCompare(b.t))
  const json = JSON.stringify(sorted)
  const encoded = new TextEncoder().encode(json)
  const buffer = await crypto.subtle.digest('SHA-256', encoded)
  const hex = Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
  return hex.slice(0, 16)
}

export function buildSummarizerArticles(articles: NewsArticle[]): NewsArticleItem[] {
  return sortByPublishedDesc(articles)
    .slice(0, 30)
    .map((a) => ({
      title: a.title || 'Untitled',
      contentText: stripHtml(a.contentHtml ?? ''),
      tickers: a.symbols.slice(0, 20),
      publishedAt: a.publishedAt,
    }))
}
