import { apiFetch } from '@/lib/api/client'

export type SetupType =
  | 'BREAKOUT'
  | 'RECLAIM'
  | 'EARNINGS_DRIFT'
  | 'EXTENDED'
  | 'BROKEN'
  | 'NONE'
  | 'CAPITULATION'

export type SetupQuality = 'A' | 'B' | 'C' | null

export type VolumeStatus = 'HIGH' | 'NORMAL' | 'LOW' | null

export type EarningsRisk = 'SAFE' | 'CAUTION' | 'DANGER'

export type SuggestedAction = 'enter' | 'watch' | 'wait' | 'reduce' | 'exit' | null

export type SetupFilterValue = 'ready' | 'near' | 'extended' | 'broken' | 'none'

export type ObvTrend = 'UP' | 'DOWN' | 'FLAT' | null

export type MacdDivergence = 'bearish' | 'bullish' | null

export type SetupItem = {
  ticker: string
  stockName: string
  setupType: SetupType
  setupQuality: SetupQuality
  entryPrice: number
  stopPrice: number
  target2r: number
  target3r: number
  distanceToEntryPct: number
  rewardRisk: number
  rsPercentile: number
  volumeStatus: VolumeStatus
  trendScore: number
  earningsRisk: EarningsRisk
  readySignal: boolean
  suggestedAction: SuggestedAction
  scanDate: string
  volumeZscore: number | null
  obvTrend: ObvTrend
  upDownVolumeRatio: number | null
  weeklyStage: number | null
  macdDivergence: MacdDivergence
}

export type SetupSummary = {
  total: number
  ready: number
  near: number
  extended: number
  broken: number
  none: number
}

export type SetupMonitorData = {
  summary: SetupSummary
  items: SetupItem[]
}

export function getSetupMonitor(filters?: SetupFilterValue[]): Promise<SetupMonitorData> {
  const qs =
    filters && filters.length > 0 ? `?filter=${filters.join(',')}` : ''
  return apiFetch<SetupMonitorData>(`/cockpit/setup-monitor${qs}`)
}
