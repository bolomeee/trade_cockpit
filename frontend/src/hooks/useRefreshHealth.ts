import { useQuery } from '@tanstack/react-query'

import { getRefreshHealth } from '@/lib/api/refreshHealth'

const POLL_INTERVAL_MS = 60_000

/**
 * D108 / F221: polls /api/refresh-health so TopNav can surface a badge when a
 * scheduled refresh job is stale or recently errored. Staleness is derived from
 * table data, so it survives the 7-day system_logs purge.
 */
export function useRefreshHealth() {
  const { data } = useQuery({
    queryKey: ['refresh-health'],
    queryFn: getRefreshHealth,
    refetchInterval: POLL_INTERVAL_MS,
    staleTime: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
  })

  const universeStale = data?.universe?.stale ?? false
  const breakoutStale = data?.breakout?.stale ?? false
  const recentErrors = data?.recentErrors ?? 0
  const hasIssue = universeStale || breakoutStale || recentErrors > 0

  const reasons: string[] = []
  if (universeStale) {
    const age = data?.universe?.ageDays
    reasons.push(`Universe 数据陈旧${age != null ? `（${Math.round(age)} 天未刷新）` : ''}`)
  }
  if (breakoutStale) {
    const age = data?.breakout?.ageDays
    reasons.push(`扫描数据陈旧${age != null ? `（${Math.round(age)} 天未刷新）` : ''}`)
  }
  if (recentErrors > 0) {
    reasons.push(`近 24h 有 ${recentErrors} 条刷新错误`)
  }

  return { hasIssue, reasons, recentErrors, data }
}
