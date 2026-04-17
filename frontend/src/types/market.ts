export type MarketSymbol = 'SPX' | 'NDX' | 'TNX'

export interface MarketIndexItem {
  symbol: MarketSymbol
  name: string
  close: number
  prevClose: number | null
  changePct: number | null
  date: string
}
