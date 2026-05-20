import { describe, it, expect } from 'vitest'
import { COCKPIT_WIDGET_REGISTRY, getCockpitDefaultLayout } from '../CockpitRegistry'

describe('S9 – CockpitRegistry cockpit.cockpit-chart', () => {
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

describe('S14 – CockpitRegistry cockpit.decision-panel', () => {
  it('cockpit.decision-panel entry exists', () => {
    expect(COCKPIT_WIDGET_REGISTRY['cockpit.decision-panel']).toBeDefined()
  })

  it('category is decision', () => {
    expect(COCKPIT_WIDGET_REGISTRY['cockpit.decision-panel'].category).toBe('decision')
  })

  it('defaultLayout matches contract (x=9 y=0 w=3 h=10 minW=3 minH=8)', () => {
    const layout = COCKPIT_WIDGET_REGISTRY['cockpit.decision-panel'].defaultLayout
    expect(layout).toMatchObject({ x: 9, y: 0, w: 3, h: 10, minW: 3, minH: 8 })
  })
})

// D1/D2 – cockpit.repricing-trigger (F218-d7b)
describe('D1 – CockpitRegistry cockpit.repricing-trigger', () => {
  it('entry exists with category=repricing', () => {
    const manifest = COCKPIT_WIDGET_REGISTRY['cockpit.repricing-trigger']
    expect(manifest).toBeDefined()
    expect(manifest.category).toBe('repricing')
    expect(manifest.title).toBe('Repricing Triggers')
  })
})

describe('D2 – getCockpitDefaultLayout includes repricing-trigger layout', () => {
  it('layout item with i="cockpit.repricing-trigger" has x=6 y=43 w=6 h=10', () => {
    const items = getCockpitDefaultLayout()
    const found = items.find((item) => item.i === 'cockpit.repricing-trigger')
    expect(found).toBeDefined()
    expect(found).toMatchObject({ x: 6, y: 43, w: 6, h: 10 })
  })
})

// S18 – cockpit.position-list
describe('S18 – CockpitRegistry cockpit.position-list', () => {
  it('entry exists with category=position', () => {
    const manifest = COCKPIT_WIDGET_REGISTRY['cockpit.position-list']
    expect(manifest).toBeDefined()
    expect(manifest.category).toBe('position')
    expect(manifest.title).toBe('Positions')
  })

  it('defaultLayout matches contract (x=0 y=8 w=6 h=8 minW=4 minH=6)', () => {
    const layout = COCKPIT_WIDGET_REGISTRY['cockpit.position-list'].defaultLayout
    expect(layout).toMatchObject({ x: 0, y: 8, w: 6, h: 8, minW: 4, minH: 6 })
  })

  it('getCockpitDefaultLayout() includes cockpit.position-list', () => {
    const items = getCockpitDefaultLayout()
    const found = items.find((item) => item.i === 'cockpit.position-list')
    expect(found).toBeDefined()
    expect(found?.x).toBe(0)
    expect(found?.y).toBe(8)
  })
})
