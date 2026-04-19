import type { ComponentType } from 'react'
import type { LayoutItem } from 'react-grid-layout'
import { ChartWidget } from './widgets/ChartWidget'
import { FundamentalsWidget } from './widgets/FundamentalsWidget'
import { PullbackWidget } from './widgets/PullbackWidget'
import { WatchlistWidget } from './widgets/WatchlistWidget'
import { JournalWidget } from './widgets/JournalWidget'
import { LogsWidget } from './widgets/LogsWidget'
import { MarketOverviewWidget } from './widgets/MarketOverviewWidget'
import { QuickAddWidget } from './widgets/QuickAddWidget'

export type WidgetCategory = 'sma150' | 'journal' | 'logs' | 'market'

export type WidgetManifest = {
  id: string
  title: string
  component: ComponentType
  defaultLayout: Omit<LayoutItem, 'i'>
  category: WidgetCategory
}

export const WIDGET_REGISTRY: Record<string, WidgetManifest> = {
  'market.overview': {
    id: 'market.overview',
    title: 'Market Overview',
    component: MarketOverviewWidget,
    defaultLayout: { x: 0, y: 0, w: 12, h: 2, minW: 6, minH: 2 },
    category: 'market',
  },
  'sma150.chart': {
    id: 'sma150.chart',
    title: 'Price Chart',
    component: ChartWidget,
    defaultLayout: { x: 0, y: 2, w: 8, h: 8, minW: 4, minH: 4 },
    category: 'sma150',
  },
  'sma150.fundamentals': {
    id: 'sma150.fundamentals',
    title: 'Fundamentals',
    component: FundamentalsWidget,
    defaultLayout: { x: 8, y: 2, w: 4, h: 4, minW: 3, minH: 3 },
    category: 'sma150',
  },
  'sma150.pullbacks': {
    id: 'sma150.pullbacks',
    title: 'Pullback History',
    component: PullbackWidget,
    defaultLayout: { x: 8, y: 6, w: 4, h: 4, minW: 3, minH: 4 },
    category: 'sma150',
  },
  'sma150.watchlist': {
    id: 'sma150.watchlist',
    title: 'Watchlist',
    component: WatchlistWidget,
    defaultLayout: { x: 0, y: 10, w: 8, h: 8, minW: 4, minH: 5 },
    category: 'sma150',
  },
  'journal.quickadd': {
    id: 'journal.quickadd',
    title: 'Quick Add',
    component: QuickAddWidget,
    defaultLayout: { x: 8, y: 10, w: 4, h: 8, minW: 3, minH: 6 },
    category: 'journal',
  },
  'journal.list': {
    id: 'journal.list',
    title: 'Trade Journal',
    component: JournalWidget,
    defaultLayout: { x: 0, y: 18, w: 12, h: 8, minW: 6, minH: 5 },
    category: 'journal',
  },
  'logs.list': {
    id: 'logs.list',
    title: 'Logs',
    component: LogsWidget,
    defaultLayout: { x: 0, y: 26, w: 12, h: 6, minW: 6, minH: 4 },
    category: 'logs',
  },
}

export function getDefaultLayout(): LayoutItem[] {
  return Object.values(WIDGET_REGISTRY).map((m) => ({ i: m.id, ...m.defaultLayout }))
}
