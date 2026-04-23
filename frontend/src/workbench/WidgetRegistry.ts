import type { ComponentType } from 'react'
import type { LayoutItem } from 'react-grid-layout'
import { ChartWidget } from './widgets/ChartWidget'
import { FundamentalsWidget } from './widgets/FundamentalsWidget'
import { MarketBreakoutWidget } from './widgets/MarketBreakoutWidget'
import { NewsWidget } from './widgets/NewsWidget'
import { PullbackWidget } from './widgets/PullbackWidget'
import { WatchlistWidget } from './widgets/WatchlistWidget'
import { QuickAddWidget } from './widgets/QuickAddWidget'

export type WidgetCategory = 'sma150' | 'journal' | 'scanner' | 'news'

export type WidgetManifest = {
  id: string
  title: string
  component: ComponentType
  defaultLayout: Omit<LayoutItem, 'i'>
  category: WidgetCategory
}

export const WIDGET_REGISTRY: Record<string, WidgetManifest> = {
  'sma150.chart': {
    id: 'sma150.chart',
    title: 'Price Chart',
    component: ChartWidget,
    defaultLayout: { x: 0, y: 0, w: 8, h: 8, minW: 4, minH: 4 },
    category: 'sma150',
  },
  'sma150.fundamentals': {
    id: 'sma150.fundamentals',
    title: 'Fundamentals',
    component: FundamentalsWidget,
    defaultLayout: { x: 8, y: 0, w: 4, h: 4, minW: 3, minH: 3 },
    category: 'sma150',
  },
  'sma150.pullbacks': {
    id: 'sma150.pullbacks',
    title: 'Pullback History',
    component: PullbackWidget,
    defaultLayout: { x: 8, y: 4, w: 4, h: 4, minW: 3, minH: 4 },
    category: 'sma150',
  },
  'sma150.watchlist': {
    id: 'sma150.watchlist',
    title: 'Watchlist',
    component: WatchlistWidget,
    defaultLayout: { x: 0, y: 8, w: 8, h: 14, minW: 4, minH: 5 },
    category: 'sma150',
  },
  'journal.quickadd': {
    id: 'journal.quickadd',
    title: 'Quick Add',
    component: QuickAddWidget,
    defaultLayout: { x: 8, y: 8, w: 4, h: 8, minW: 3, minH: 6 },
    category: 'journal',
  },
  'scanner.breakouts': {
    id: 'scanner.breakouts',
    title: 'Market Breakouts',
    component: MarketBreakoutWidget,
    defaultLayout: { x: 0, y: 16, w: 8, h: 8, minW: 5, minH: 5 },
    category: 'scanner',
  },
  'news.table': {
    id: 'news.table',
    title: 'News',
    component: NewsWidget,
    defaultLayout: { x: 0, y: 0, w: 12, h: 14, minW: 6, minH: 6 },
    category: 'news',
  },
}

export function getWorkbenchDefaultLayout(): LayoutItem[] {
  return Object.values(WIDGET_REGISTRY)
    .filter((m) => m.category !== 'news')
    .map((m) => ({ i: m.id, ...m.defaultLayout }))
}

export function getNewsDefaultLayout(): LayoutItem[] {
  return Object.values(WIDGET_REGISTRY)
    .filter((m) => m.category === 'news')
    .map((m) => ({ i: m.id, ...m.defaultLayout }))
}
