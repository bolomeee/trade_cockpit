export interface PullbackEntry {
  date: string
  closePrice: number
  ma150Value: number
  distancePct: number
  return10d: number | null
  return20d: number | null
  return30d: number | null
}

export interface Fundamentals {
  ticker: string
  priceToEarnings: number
  priceToSales: number
  peg: number
  roce?: number | null
  freeCashFlow: number
  marketCap: number
  source: string
  updatedAt: string
}

export interface ChartBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface ChartMa150Point {
  date: string
  value: number
}

export interface ChartPullbackMarker {
  date: string
  distancePct: number
}

export interface ChartData {
  ticker: string
  bars: ChartBar[]
  ma150: ChartMa150Point[]
  pullbackMarkers: ChartPullbackMarker[]
}
