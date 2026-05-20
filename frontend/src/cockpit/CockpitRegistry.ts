import type { ComponentType } from 'react'
import type { LayoutItem } from 'react-grid-layout'
import { MarketRegimeWidget } from './widgets/MarketRegimeWidget'
import { SetupMonitorWidget } from './widgets/SetupMonitorWidget'
import { CockpitChartWidget } from './widgets/CockpitChartWidget'
import { DecisionPanelWidget } from './widgets/DecisionPanelWidget'
import { PositionListWidget } from './widgets/PositionListWidget'
import { PendingOrdersWidget } from './widgets/PendingOrdersWidget'
import { ActionListWidget } from './widgets/ActionListWidget'
import { PoolBuilderWidget } from './widgets/PoolBuilderWidget'
import { WeeklyStageChartWidget } from './widgets/WeeklyStageChartWidget'
import { RepricingTriggerWidget } from './widgets/RepricingTriggerWidget'

export type CockpitWidgetCategory =
  | 'regime'
  | 'setup'
  | 'decision'
  | 'chart'
  | 'earnings'
  | 'position'
  | 'pool'
  | 'action'
  | 'repricing'

export type CockpitWidgetManifest = {
  id: string
  title: string
  component: ComponentType
  defaultLayout: Omit<LayoutItem, 'i'>
  category: CockpitWidgetCategory
}

// Default layout = "Opportunity Discovery Terminal" (Bloomberg-style funnel)
// Lane 1 (y=0,  h=8 ): Market Regime — full-width context ribbon
// Lane 2 (y=8,  h=10): Pool Builder | Setup Monitor — discovery engine
// Lane 3 (y=18, h=10): Cockpit Chart | Weekly Stage | Decision Panel — drill-down
// Lane 4 (y=28, h=8 ): Position List | Repricing Trigger — risk & exit
// Lane 5 (y=36, h=6 ): Today's Actions — execution queue
export const COCKPIT_WIDGET_REGISTRY: Record<string, CockpitWidgetManifest> = {
  'cockpit.market-regime': {
    id: 'cockpit.market-regime',
    title: 'Market Regime',
    component: MarketRegimeWidget,
    defaultLayout: { x: 0, y: 0, w: 12, h: 8, minW: 3, minH: 4 },
    category: 'regime',
  },
  'cockpit.pool-builder': {
    id: 'cockpit.pool-builder',
    title: 'Pool Builder',
    component: PoolBuilderWidget,
    defaultLayout: { x: 0, y: 8, w: 6, h: 10, minW: 6, minH: 6 },
    category: 'pool',
  },
  'cockpit.setup-monitor': {
    id: 'cockpit.setup-monitor',
    title: 'Setup Monitor',
    component: SetupMonitorWidget,
    defaultLayout: { x: 6, y: 8, w: 6, h: 10, minW: 6, minH: 6 },
    category: 'setup',
  },
  'cockpit.cockpit-chart': {
    id: 'cockpit.cockpit-chart',
    title: 'Cockpit Chart',
    component: CockpitChartWidget,
    defaultLayout: { x: 0, y: 18, w: 5, h: 10, minW: 4, minH: 8 },
    category: 'chart',
  },
  'cockpit.weekly-stage': {
    id: 'cockpit.weekly-stage',
    title: 'Weekly Stage',
    component: WeeklyStageChartWidget,
    defaultLayout: { x: 5, y: 18, w: 4, h: 10, minW: 3, minH: 8 },
    category: 'chart',
  },
  'cockpit.decision-panel': {
    id: 'cockpit.decision-panel',
    title: 'Decision Panel',
    component: DecisionPanelWidget,
    defaultLayout: { x: 9, y: 18, w: 3, h: 10, minW: 3, minH: 8 },
    category: 'decision',
  },
  'cockpit.position-list': {
    id: 'cockpit.position-list',
    title: 'Positions',
    component: PositionListWidget,
    defaultLayout: { x: 0, y: 28, w: 8, h: 8, minW: 4, minH: 6 },
    category: 'position',
  },
  'cockpit.repricing-trigger': {
    id: 'cockpit.repricing-trigger',
    title: 'Repricing Triggers',
    component: RepricingTriggerWidget,
    defaultLayout: { x: 8, y: 28, w: 4, h: 8, minW: 4, minH: 6 },
    category: 'repricing',
  },
  'cockpit.action-list': {
    id: 'cockpit.action-list',
    title: "Today's Actions",
    component: ActionListWidget,
    defaultLayout: { x: 0, y: 36, w: 12, h: 6, minW: 6, minH: 4 },
    category: 'action',
  },
  'cockpit.pending-orders': {
    id: 'cockpit.pending-orders',
    title: 'Pending Orders',
    component: PendingOrdersWidget,
    defaultLayout: { x: 0, y: 42, w: 6, h: 8, minW: 4, minH: 4 },
    category: 'position',
  },
}

// pending-orders is registered (so it can be added from the picker) but is NOT
// part of the Opportunity Discovery default layout — execution-side noise is
// folded into "Today's Actions".
const DEFAULT_LAYOUT_HIDDEN = new Set<string>(['cockpit.pending-orders'])

export function getCockpitDefaultLayout(): LayoutItem[] {
  return Object.values(COCKPIT_WIDGET_REGISTRY)
    .filter((m) => !DEFAULT_LAYOUT_HIDDEN.has(m.id))
    .map((m) => ({ i: m.id, ...m.defaultLayout }))
}
