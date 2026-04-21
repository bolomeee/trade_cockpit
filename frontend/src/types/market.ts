export type MarketSymbol = 'SPX' | 'NDX' | 'TNX'

export interface MarketIndexItem {
  symbol: MarketSymbol
  name: string
  close: number
  prevClose: number | null
  changePct: number | null
  date: string
}

export interface BreakoutItem {
  ticker: string
  companyName: string
  closePrice: number
  ma150Value: number
  pctAboveMa150: number
  marketCap: number
}

export interface BreakoutSnapshot {
  scanDate: string | null
  scannedAt: string | null
  items: BreakoutItem[]
  total: number
}
