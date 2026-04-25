import { apiFetch } from '@/lib/api/client'
import type { SetupType } from './setupMonitorApi'

export type RegimeLabel = 'RISK_ON' | 'CONSTRUCTIVE' | 'NEUTRAL' | 'DEFENSIVE' | 'RISK_OFF'
export type IndexState = 'Bullish' | 'Leading' | 'Constructive' | 'Neutral' | 'Weak' | 'Defensive'
export type SectorState = 'Strong' | 'Constructive' | 'Weak' | 'Defensive' | 'Neutral'
export type RsTrend = 'up' | 'down' | 'flat'

export type RegimeSubscores = {
  spyTrend: number
  qqqTrend: number
  iwmBreadth: number
  sectorParticipation: number
  riskAppetite: number
  volatilityStress: number
}

export type RegimeIndex = {
  symbol: string
  close: number
  changePct: number
  aboveMa50: boolean
  aboveMa200: boolean
  rsTrend: RsTrend
  state: IndexState
}

export type RegimeSector = {
  symbol: string
  close: number | null
  changePct: number | null
  state: SectorState
}

export type CockpitRegimeData = {
  date: string
  regime: RegimeLabel
  marketScore: number
  subscores: RegimeSubscores
  allowedExposurePct: number
  singleTradeRiskPct: number
  preferredSetups: SetupType[]
  avoidSetups: SetupType[]
  indices: RegimeIndex[]
  sectors: RegimeSector[]
  computedAt: string
}

export function getCockpitRegime(): Promise<CockpitRegimeData> {
  return apiFetch<CockpitRegimeData>('/cockpit/regime')
}
