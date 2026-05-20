import { apiFetch } from '@/lib/api/client'

export type TriggerType =
  | 'EARNINGS_ACCEL'
  | 'MARGIN_EXPANSION'
  | 'NEW_PRODUCT'
  | 'SECTOR_CYCLE'
  | 'BALANCE_INFLECTION'

export type EarningsAccelEvidence = {
  epsYoyGrowth: number[]
  revenueYoyGrowth: number[]
  quarters: string[]
}
export type MarginExpansionEvidence = {
  grossMarginTrend: number[]
  fcfMarginTrend: number[]
  quarters: string[]
  triggerMetric: 'gross_margin' | 'fcf_margin'
  expansionBp: number
}
export type NewProductEvidence = {
  keywordHits: Record<string, number>
  newsLinks: Array<{ title: string; url: string; publishedAt: string }>
}
export type SectorCycleEvidence = {
  sector: string
  rsHistory: number[]
  priceVs200d: number
}
export type BalanceInflectionEvidence = {
  netDebtTrend: number[]
  fcfTrend: number[]
  quarters: string[]
  triggerMetric: 'net_debt' | 'fcf'
}
export type TriggerEvidence =
  | EarningsAccelEvidence
  | MarginExpansionEvidence
  | NewProductEvidence
  | SectorCycleEvidence
  | BalanceInflectionEvidence

export type RepricingTrigger = {
  triggerType: TriggerType
  detectedDate: string
  confidence: number
  evidence: TriggerEvidence
  computedAt: string
}
export type RepricingTriggerWithTicker = RepricingTrigger & { ticker: string }

export type TickerTriggersPayload = {
  ticker: string
  triggers: RepricingTrigger[]
}
export type AllTriggersPayload = {
  triggers: RepricingTriggerWithTicker[]
  totalCount: number
  computedAt: string
}

export type GetAllActiveTriggersOptions = {
  triggerType?: TriggerType
  limit?: number
}

export function getTickerRepricingTriggers(ticker: string): Promise<TickerTriggersPayload> {
  return apiFetch<TickerTriggersPayload>(
    `/cockpit/repricing-triggers/${ticker.toUpperCase()}`,
  )
}

export function getAllActiveTriggers(opts?: GetAllActiveTriggersOptions): Promise<AllTriggersPayload> {
  const params = new URLSearchParams()
  if (opts?.triggerType != null) params.set('triggerType', opts.triggerType)
  if (opts?.limit != null) params.set('limit', String(opts.limit))
  const qs = params.toString() ? `?${params.toString()}` : ''
  return apiFetch<AllTriggersPayload>(`/cockpit/repricing-triggers${qs}`)
}
