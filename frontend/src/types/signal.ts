import type { SignalType } from './watchlist'

export type { SignalType }

export type LabelColor = 'red' | 'yellow' | 'blue' | null

export interface SignalBoardItem {
  ticker: string
  name: string
  signalType: SignalType
  date: string | null
  closePrice: number | null
  ma150Value: number | null
  distancePct: number | null
  slopePositive: boolean | null
  slopeValue: number | null
  labelColor: LabelColor
}
