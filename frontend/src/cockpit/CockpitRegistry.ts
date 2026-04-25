import type { ComponentType } from 'react'
import type { LayoutItem } from 'react-grid-layout'
import { MarketRegimeWidget } from './widgets/MarketRegimeWidget'
import { SetupMonitorWidget } from './widgets/SetupMonitorWidget'
import { CockpitChartWidget } from './widgets/CockpitChartWidget'
import { DecisionPanelWidget } from './widgets/DecisionPanelWidget'

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
  'cockpit.market-regime': {
    id: 'cockpit.market-regime',
    title: 'Market Regime',
    component: MarketRegimeWidget,
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
  'cockpit.cockpit-chart': {
    id: 'cockpit.cockpit-chart',
    title: 'Cockpit Chart',
    component: CockpitChartWidget,
    defaultLayout: { x: 4, y: 0, w: 5, h: 10, minW: 4, minH: 8 },
    category: 'chart',
  },
  'cockpit.decision-panel': {
    id: 'cockpit.decision-panel',
    title: 'Decision Panel',
    component: DecisionPanelWidget,
    defaultLayout: { x: 9, y: 0, w: 3, h: 10, minW: 3, minH: 8 },
    category: 'decision',
  },
}

export function getCockpitDefaultLayout(): LayoutItem[] {
  return Object.values(COCKPIT_WIDGET_REGISTRY).map((m) => ({ i: m.id, ...m.defaultLayout }))
}
