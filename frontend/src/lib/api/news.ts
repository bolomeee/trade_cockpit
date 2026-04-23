import { apiFetch } from './client'
import type { NewsArticle } from '@/types/news'

export interface NewsArticlesParams {
  limit?: number
  since?: string  // ISO-8601
  window?: 'calendar-1d' | 'none'
}

export function getNewsArticles(params?: NewsArticlesParams): Promise<NewsArticle[]> {
  const qs = new URLSearchParams()
  if (params?.limit !== undefined) qs.set('limit', String(params.limit))
  if (params?.since) qs.set('since', params.since)
  if (params?.window) qs.set('window', params.window)
  const query = qs.toString()
  return apiFetch<NewsArticle[]>(`/news/articles${query ? `?${query}` : ''}`)
}
