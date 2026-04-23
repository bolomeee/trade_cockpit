import type { NewsArticle } from '@/types/news'

const STORAGE_KEY = 'ma150.news.v1'
const RETENTION_DAYS = 5

function cutoffIso(): string {
  const d = new Date()
  d.setDate(d.getDate() - RETENTION_DAYS)
  d.setUTCHours(0, 0, 0, 0)
  return d.toISOString()
}

export function articleKey(a: NewsArticle): string {
  return a.url ?? `${a.publishedAt.slice(0, 19)}|${a.title.slice(0, 80)}`
}

export function loadArticles(): NewsArticle[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as NewsArticle[]) : null
  } catch {
    return null
  }
}

export function saveArticles(articles: NewsArticle[]): void {
  try {
    const cutoff = cutoffIso()
    const pruned = articles.filter((a) => a.publishedAt >= cutoff)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pruned))
  } catch {
    // quota exceeded — silently skip
  }
}

export function latestPublishedAt(articles: NewsArticle[]): string | null {
  return articles.length > 0 ? articles[0].publishedAt : null
}

export function mergeArticles(
  existing: NewsArticle[],
  incoming: NewsArticle[],
): NewsArticle[] {
  const seen = new Set(existing.map(articleKey))
  const fresh = incoming.filter((a) => !seen.has(articleKey(a)))
  return [...fresh, ...existing]
}

export function fiveDaysAgoIso(): string {
  return cutoffIso()
}
