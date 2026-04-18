import type { ComponentType } from 'react'
import type { LayoutItem } from 'react-grid-layout'
import { DemoWidget } from './widgets/DemoWidget'

export type WidgetCategory = 'sma150' | 'journal' | 'logs' | 'market' | 'demo'

export type WidgetManifest = {
  id: string
  title: string
  component: ComponentType
  defaultLayout: Omit<LayoutItem, 'i'>
  category: WidgetCategory
}

export const WIDGET_REGISTRY: Record<string, WidgetManifest> = {
  'demo.a': {
    id: 'demo.a',
    title: 'Demo Widget A',
    component: DemoWidget,
    defaultLayout: { x: 0, y: 0, w: 4, h: 4, minW: 2, minH: 2 },
    category: 'demo',
  },
  'demo.b': {
    id: 'demo.b',
    title: 'Demo Widget B',
    component: DemoWidget,
    defaultLayout: { x: 4, y: 0, w: 4, h: 4, minW: 2, minH: 2 },
    category: 'demo',
  },
  'demo.c': {
    id: 'demo.c',
    title: 'Demo Widget C',
    component: DemoWidget,
    defaultLayout: { x: 8, y: 0, w: 4, h: 4, minW: 2, minH: 2 },
    category: 'demo',
  },
}

export function getDefaultLayout(): LayoutItem[] {
  return Object.values(WIDGET_REGISTRY).map((m) => ({ i: m.id, ...m.defaultLayout }))
}
