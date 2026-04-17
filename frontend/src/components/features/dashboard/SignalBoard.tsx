import type { SignalBoardItem, SignalType } from '@/types/signal'
import { SignalCard } from './SignalCard'

const SIGNAL_PRIORITY: Record<SignalType, number> = {
  BREAKOUT: 0,
  BUY_ZONE: 1,
  NEUTRAL: 2,
  INSUFFICIENT: 3,
}

interface SignalBoardProps {
  stocks: SignalBoardItem[]
  onSelectStock: (stock: SignalBoardItem) => void
}

export function SignalBoard({ stocks, onSelectStock }: SignalBoardProps) {
  const sorted = [...stocks].sort(
    (a, b) => (SIGNAL_PRIORITY[a.signalType] ?? 3) - (SIGNAL_PRIORITY[b.signalType] ?? 3),
  )

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {sorted.map(stock => (
        <SignalCard
          key={stock.ticker}
          stock={stock}
          onClick={() => onSelectStock(stock)}
        />
      ))}
    </div>
  )
}
