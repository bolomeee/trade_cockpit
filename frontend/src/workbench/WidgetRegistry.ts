import type { ComponentType } from 'react'
import type { LayoutItem } from 'react-grid-layout'
import { DemoWidget } from './widgets/DemoWidget'
import { ChartWidget } from './widgets/ChartWidget'
import { FundamentalsWidget } from './widgets/FundamentalsWidget'
import { PullbackWidget } from './widgets/PullbackWidget'

export type WidgetCategory = 'sma150' | 'journal' | 'logs' | 'market' | 'demo'

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
    defaultLayout: { x: 8, y: 4, w: 4, h: 8, minW: 3, minH: 4 },
    category: 'sma150',
  },
  'demo.controls': {
    id: 'demo.controls',
    title: 'Symbol Controls (dev)',
    component: DemoWidget,
    defaultLayout: { x: 0, y: 8, w: 8, h: 3, minW: 3, minH: 2 },
    category: 'demo',
  },
}

export function getDefaultLayout(): LayoutItem[] {
  return Object.values(WIDGET_REGISTRY).map((m) => ({ i: m.id, ...m.defaultLayout }))
}
