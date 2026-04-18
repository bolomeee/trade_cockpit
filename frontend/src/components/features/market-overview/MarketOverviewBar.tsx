import { useMarketOverview } from '@/hooks/useMarketOverview'
import type { MarketIndexItem, MarketSymbol } from '@/types/market'

const DISPLAY_ORDER: MarketSymbol[] = ['SPX', 'NDX', 'TNX']

const DISPLAY_NAME: Record<MarketSymbol, string> = {
  SPX: 'S&P 500',
  NDX: 'NASDAQ 100',
  TNX: '10Y Treasury',
}

function formatClose(symbol: MarketSymbol, close: number): string {
  if (symbol === 'TNX') return `${close.toFixed(2)}%`
  return close.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatChangePct(pct: number | null): string {
  if (pct === null || Number.isNaN(pct)) return '—'
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

function changeColor(pct: number | null): string {
  if (pct === null || Number.isNaN(pct)) return 'var(--color-text-secondary)'
  return pct >= 0 ? 'var(--color-change-positive)' : 'var(--color-change-negative)'
}

function bySymbol(items: MarketIndexItem[] | undefined): Partial<Record<MarketSymbol, MarketIndexItem>> {
  const map: Partial<Record<MarketSymbol, MarketIndexItem>> = {}
  for (const item of items ?? []) map[item.symbol] = item
  return map
}

export function MarketOverviewBar() {
  const { data } = useMarketOverview()

  const map = bySymbol(data)

  return (
    <div
      style={{
        height: '41.78px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--spacing-8, 32px)',
        backgroundColor: 'var(--color-background)',
        borderBottom: '1px solid var(--color-border)',
        fontSize: 'var(--font-size-market-bar)',
      }}
      data-testid="market-overview-bar"
    >
      {DISPLAY_ORDER.map((symbol) => {
        const item = map[symbol]
        return (
          <div
            key={symbol}
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2, 8px)' }}
            data-testid={`market-cell-${symbol}`}
          >
            <span style={{ color: 'var(--color-text-secondary)' }}>{DISPLAY_NAME[symbol]}</span>
            <span style={{ color: 'var(--color-text-primary)', fontWeight: 'var(--font-weight-bold)' }}>
              {item ? formatClose(symbol, item.close) : '—'}
            </span>
            <span style={{ color: changeColor(item?.changePct ?? null) }}>
              {item ? formatChangePct(item.changePct) : '—'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
