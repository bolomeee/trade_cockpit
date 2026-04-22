import { useQuery } from '@tanstack/react-query'
import { getNewsArticles } from '@/lib/api/news'

const STALE_MS = 60 * 1000

export function useNewsArticles(limit?: number) {
  return useQuery({
    queryKey: ['news', 'articles', limit ?? 'default'],
    queryFn: () => getNewsArticles(limit),
    staleTime: STALE_MS,
  })
}
