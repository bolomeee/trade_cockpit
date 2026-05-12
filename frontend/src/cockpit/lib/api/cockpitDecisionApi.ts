import { apiFetch } from '@/lib/api/client'
import type { SetupType, SetupQuality, EarningsRisk } from './setupMonitorApi'

export type CockpitDecisionData = {
  ticker: string
  setupType: SetupType
  setupQuality: SetupQuality
  entryPrice: number
  stopPrice: number
  target2r: number
  target3r: number
  rewardRisk: number
  riskPerShare: number
  suggestedShares: number
  positionValue: number
  accountRiskPct: number
  effectiveRiskPct: number
  regimeCap: number
  userSettingCap: number
  earningsRisk: EarningsRisk | null
  earningsDate: string | null
  deterministicHash: string
}

export type GetCockpitDecisionOverrides = {
  entryOverride?: number
  stopOverride?: number
  riskPctOverride?: number
}

export function getCockpitDecision(
  ticker: string,
  overrides?: GetCockpitDecisionOverrides,
): Promise<CockpitDecisionData> {
  const params = new URLSearchParams()
  if (overrides?.entryOverride != null) params.set('entryOverride', String(overrides.entryOverride))
  if (overrides?.stopOverride != null) params.set('stopOverride', String(overrides.stopOverride))
  if (overrides?.riskPctOverride != null)
    params.set('riskPctOverride', String(overrides.riskPctOverride))
  const qs = params.toString()
  return apiFetch<CockpitDecisionData>(`/cockpit/decision/${ticker}${qs ? `?${qs}` : ''}`)
}
