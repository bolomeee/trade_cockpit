import { apiFetch } from '@/lib/api/client'

export type ChartBarItem = {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export type ChartSeriesPoint = {
  date: string
  value: number
}

export type ChartAvwap = {
  anchor: string | null
  series: ChartSeriesPoint[]
}

export type CockpitChartData = {
  ticker: string
  bars: ChartBarItem[]
  mas: Record<string, ChartSeriesPoint[]>
  emas: Record<string, ChartSeriesPoint[]>
  atr: ChartSeriesPoint[]
  avwap: ChartAvwap
}

const DEFAULT_MAS = [10, 21, 50, 150, 200]
const DEFAULT_DAYS = 250

export type GetCockpitChartOptions = {
  mas?: number[]
  days?: number
  anchor?: string
}

export function getCockpitChart(
  ticker: string,
  options?: GetCockpitChartOptions,
): Promise<CockpitChartData> {
  const mas = options?.mas ?? DEFAULT_MAS
  const days = options?.days ?? DEFAULT_DAYS
  const parts = [`mas=${mas.join(',')}`, `days=${days}`]
  if (options?.anchor) parts.push(`anchor=${options.anchor}`)
  return apiFetch<CockpitChartData>(`/cockpit/chart/${ticker}?${parts.join('&')}`)
}
