import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getNewsArticles } from '@/lib/api/news'
import {
  fiveDaysAgoIso,
  latestPublishedAt,
  loadArticles,
  mergeArticles,
  saveArticles,
} from '@/lib/news-persist'
import type { NewsArticle } from '@/types/news'

const QUERY_KEY = ['news', 'articles'] as const
const DEFAULT_LIMIT = 200

export function useNewsArticles(limit = DEFAULT_LIMIT) {
  const queryClient = useQueryClient()
  // Read once on mount — keeps initialData stable across re-renders so React
  // Query's internal hook count stays consistent (avoids Rules-of-Hooks violation).
  const [persisted] = useState(() => loadArticles())

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => getNewsArticles({ since: fiveDaysAgoIso(), limit }),
    initialData: persisted ?? undefined,
    // 5min: instant render from localStorage, background refetch on stale.
    // Previously `persisted ? Infinity : 0` froze cached views forever.
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (query.data) saveArticles(query.data)
  }, [query.data])

  const refreshMutation = useMutation({
    mutationFn: async (): Promise<NewsArticle[]> => {
      const current = queryClient.getQueryData<NewsArticle[]>(QUERY_KEY) ?? []
      const since = latestPublishedAt(current)
      return since
        ? getNewsArticles({ since })
        : getNewsArticles({ since: fiveDaysAgoIso(), limit })
    },
    onSuccess: (newArticles) => {
      queryClient.setQueryData<NewsArticle[]>(QUERY_KEY, (old) => {
        const merged = mergeArticles(old ?? [], newArticles)
        saveArticles(merged)
        return merged
      })
    },
  })

  return {
    ...query,
    refresh: () => refreshMutation.mutate(),
    isRefreshing: refreshMutation.isPending,
  }
}
