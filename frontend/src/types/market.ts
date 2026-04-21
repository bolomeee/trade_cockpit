export type MarketSymbol = 'SPX' | 'NDX' | 'TNX'

export interface MarketIndexItem {
  symbol: MarketSymbol
  name: string
  close: number
  prevClose: number | null
  changePct: number | null
  date: string
}

export type SignalType =
  | 'legacy_crossover'
  | 'a1_stage_breakout'
  | 'a2_slope_flip'
  | 'b2_ma_pullback'

export interface BreakoutItem {
  ticker: string
  companyName: string
  signalType: SignalType
  closePrice: number
  ma150Value: number
  pctAboveMa150: number
  slopeValue: number
  volume: number | null
  volumeRatio20: number | null
  marketCap: number
}

export interface BreakoutSnapshot {
  scanDate: string | null
  scannedAt: string | null
  items: BreakoutItem[]
  total: number
}
