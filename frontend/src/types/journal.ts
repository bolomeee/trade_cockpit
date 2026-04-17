export type Action = 'BUY' | 'SELL' | 'ADD' | 'REDUCE' | 'WATCH'

export const ACTIONS: Action[] = ['BUY', 'SELL', 'ADD', 'REDUCE', 'WATCH']

export interface JournalEntry {
  id: number
  ticker: string
  stockName: string
  action: Action
  price: number
  date: string
  positionSize: number | null
  stopLoss: number | null
  targetPrice: number | null
  reason: string | null
  reference: string | null
  createdAt: string
  updatedAt: string
}

export interface JournalListResponse {
  items: JournalEntry[]
  total: number
  limit: number
  offset: number
}

export interface JournalFilter {
  ticker?: string
  action?: Action
}
