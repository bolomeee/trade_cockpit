import { useCallback, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getRefreshStatus, triggerRefresh } from '@/lib/api/data'

const POLL_INTERVAL_MS = 2000
const STATUS_KEY = ['data', 'refresh-status'] as const

export function useRefreshStatus() {
  const queryClient = useQueryClient()
  const prevStatusRef = useRef<string | null>(null)

  const statusQuery = useQuery({
    queryKey: STATUS_KEY,
    queryFn: getRefreshStatus,
    refetchInterval: (query) =>
      query.state.data?.status === 'in_progress' ? POLL_INTERVAL_MS : false,
    refetchOnWindowFocus: false,
  })

  const currentStatus = statusQuery.data?.status ?? 'idle'

  // On transition to completed, invalidate watchlist + signals so SignalBoard refetches
  useEffect(() => {
    if (prevStatusRef.current === 'in_progress' && currentStatus === 'completed') {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      queryClient.invalidateQueries({ queryKey: ['signals'] })
      queryClient.invalidateQueries({ queryKey: ['market', 'overview'] })
    }
    prevStatusRef.current = currentStatus
  }, [currentStatus, queryClient])

  const mutation = useMutation({
    mutationFn: triggerRefresh,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: STATUS_KEY })
    },
    onError: (err) => {
      console.error('triggerRefresh failed', err)
    },
  })

  const refresh = useCallback(() => {
    if (currentStatus === 'in_progress' || mutation.isPending) return
    mutation.mutate()
  }, [currentStatus, mutation])

  return {
    status: currentStatus,
    lastRefreshedAt: statusQuery.data?.lastRefreshedAt ?? null,
    isRefreshing: currentStatus === 'in_progress' || mutation.isPending,
    refresh,
  }
}
