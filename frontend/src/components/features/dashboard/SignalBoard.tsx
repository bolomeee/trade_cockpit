import type { WatchlistItem, SignalType } from '@/types/watchlist'
import { SignalCard } from './SignalCard'

const SIGNAL_PRIORITY: Record<SignalType, number> = {
  BREAKOUT: 0,
  BUY_ZONE: 1,
  NEUTRAL: 2,
  INSUFFICIENT: 3,
}

function getSignalPriority(item: WatchlistItem): number {
  const type = item.latestSignal?.signalType ?? 'INSUFFICIENT'
  return SIGNAL_PRIORITY[type] ?? 3
}

interface SignalBoardProps {
  stocks: WatchlistItem[]
  onSelectStock: (ticker: string) => void
}

export function SignalBoard({ stocks, onSelectStock }: SignalBoardProps) {
  const sorted = [...stocks].sort((a, b) => getSignalPriority(a) - getSignalPriority(b))

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {sorted.map(stock => (
        <SignalCard
          key={stock.id}
          stock={stock}
          onClick={() => onSelectStock(stock.ticker)}
        />
      ))}
    </div>
  )
}
