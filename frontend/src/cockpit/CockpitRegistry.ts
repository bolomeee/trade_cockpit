import type { ComponentType } from 'react'
import type { LayoutItem } from 'react-grid-layout'
import { PlaceholderWidget } from './widgets/PlaceholderWidget'
import { SetupMonitorWidget } from './widgets/SetupMonitorWidget'

export type CockpitWidgetCategory =
  | 'regime'
  | 'setup'
  | 'decision'
  | 'chart'
  | 'earnings'
  | 'position'
  | 'pool'
  | 'action'

export type CockpitWidgetManifest = {
  id: string
  title: string
  component: ComponentType
  defaultLayout: Omit<LayoutItem, 'i'>
  category: CockpitWidgetCategory
}

export const COCKPIT_WIDGET_REGISTRY: Record<string, CockpitWidgetManifest> = {
  'cockpit.placeholder': {
    id: 'cockpit.placeholder',
    title: 'Cockpit Placeholder',
    component: PlaceholderWidget,
    defaultLayout: { x: 0, y: 0, w: 4, h: 8, minW: 3, minH: 4 },
    category: 'regime',
  },
  'cockpit.setup-monitor': {
    id: 'cockpit.setup-monitor',
    title: 'Setup Monitor',
    component: SetupMonitorWidget,
    defaultLayout: { x: 4, y: 0, w: 8, h: 10, minW: 6, minH: 6 },
    category: 'setup',
  },
}

export function getCockpitDefaultLayout(): LayoutItem[] {
  return Object.values(COCKPIT_WIDGET_REGISTRY).map((m) => ({ i: m.id, ...m.defaultLayout }))
}
