import { apiFetch } from '@/lib/api/client'

export type AiMeta = {
  modelUsed: string
  tier: string
  tokensIn: number
  tokensOut: number
  costUsd: number
  latencyMs: number
  cacheHit: boolean
}

export type AiTaskResponse<TOut> = {
  memoId: number
  taskType: string
  schemaVersion: string
  output: TOut
  meta: AiMeta
}

export type MarketNarratorInput = {
  regime: 'RISK_ON' | 'CONSTRUCTIVE' | 'NEUTRAL' | 'DEFENSIVE' | 'RISK_OFF'
  marketScore: number
  subscores: {
    spyTrend: number
    qqqTrend: number
    iwmBreadth: number
    sectorParticipation: number
    riskAppetite: number
    volatilityStress: number
  }
  sectors: Array<{
    symbol: string
    closePct: number
    state: 'Strong' | 'Neutral' | 'Weak'
  }>
}

export type MarketNarratorOutput = {
  headline: string
  summary: string
  riskPosture: 'aggressive' | 'balanced' | 'cautious' | 'defensive'
  preferredSetups: string[]
  avoid: string[]
  warnings: string[]
}

export function callAiTask<TIn, TOut>(
  taskType: string,
  input: TIn,
  opts?: { noCache?: boolean },
): Promise<AiTaskResponse<TOut>> {
  return apiFetch<AiTaskResponse<TOut>>(`/ai/${taskType}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input, noCache: !!opts?.noCache }),
  })
}
