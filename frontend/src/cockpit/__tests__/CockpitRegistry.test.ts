import { describe, it, expect } from 'vitest'
import { COCKPIT_WIDGET_REGISTRY } from '../CockpitRegistry'

describe('S9 – CockpitRegistry', () => {
  it('cockpit.cockpit-chart entry exists', () => {
    expect(COCKPIT_WIDGET_REGISTRY['cockpit.cockpit-chart']).toBeDefined()
  })

  it('category is chart', () => {
    expect(COCKPIT_WIDGET_REGISTRY['cockpit.cockpit-chart'].category).toBe('chart')
  })

  it('defaultLayout matches contract (x=4 y=0 w=5 h=10 minW=4 minH=8)', () => {
    const layout = COCKPIT_WIDGET_REGISTRY['cockpit.cockpit-chart'].defaultLayout
    expect(layout).toMatchObject({ x: 4, y: 0, w: 5, h: 10, minW: 4, minH: 8 })
  })
})
