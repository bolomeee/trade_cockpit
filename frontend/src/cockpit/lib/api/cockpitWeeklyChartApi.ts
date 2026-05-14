import { apiFetch } from '@/lib/api/client'
import type { ChartBarItem, ChartSeriesPoint } from './cockpitChartApi'

export type WeeklyStagePayload = {
  stage: number
  weeklyClose: number | null
  weeklyMa10: number | null
  weeklyMa30: number | null
  weeklyMa40: number | null
  slope30W: number | null
  scanDate: string | null
}

export type WeeklyChartData = {
  ticker: string
  weeklyBars: ChartBarItem[]
  weeklyMas: Record<string, ChartSeriesPoint[]>
  stage: WeeklyStagePayload
}

const DEFAULT_WEEKS = 50

export type GetCockpitWeeklyChartOptions = {
  weeks?: number
}

export function getCockpitWeeklyChart(
  ticker: string,
  options?: GetCockpitWeeklyChartOptions,
): Promise<WeeklyChartData> {
  const weeks = options?.weeks ?? DEFAULT_WEEKS
  return apiFetch<WeeklyChartData>(`/cockpit/chart/${ticker}/weekly?weeks=${weeks}`)
}
