import { apiFetch } from './client'
import type { NewsArticle } from '@/types/news'

export function getNewsArticles(limit?: number): Promise<NewsArticle[]> {
  const qs = limit !== undefined ? `?limit=${limit}` : ''
  return apiFetch<NewsArticle[]>(`/news/articles${qs}`)
}
