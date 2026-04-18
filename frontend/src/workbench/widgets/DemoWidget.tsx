import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '@/store/useAppStore'
import { getWatchlist } from '@/lib/api/watchlist'
import type { WatchlistItem } from '@/types/watchlist'

export function DemoWidget() {
  const { selectedSymbol, setSelectedSymbol } = useAppStore()
  const { data, isLoading } = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    staleTime: 60 * 1000,
  })
  const tickers = ((data as WatchlistItem[] | undefined) ?? []).map((w) => w.ticker)

  return (
    <div className="flex h-full flex-col gap-2 text-sm">
      <p className="text-muted-foreground">
        Selected symbol: <strong className="text-foreground">{selectedSymbol ?? '(none)'}</strong>
      </p>
      {isLoading && <p className="text-xs text-muted-foreground">loading watchlist…</p>}
      {!isLoading && tickers.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Watchlist 为空，请到 <a href="/" className="underline">Dashboard</a> 添加股票。
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {tickers.map((s) => (
          <button
            key={s}
            type="button"
            className="rounded border border-border bg-background px-2 py-1 text-xs hover:bg-muted"
            onClick={() => setSelectedSymbol(s)}
          >
            {s}
          </button>
        ))}
        {tickers.length > 0 && (
          <button
            type="button"
            className="rounded border border-border bg-background px-2 py-1 text-xs hover:bg-muted"
            onClick={() => setSelectedSymbol(null)}
          >
            clear
          </button>
        )}
      </div>
    </div>
  )
}
