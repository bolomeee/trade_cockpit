import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getTodayActions } from '../cockpitActionsApi'
import type { TodayActionsPayload, ActionItem } from '../cockpitActionsApi'

function makeOkResponse(data: unknown, status = 200) {
  return { ok: true, status, json: () => Promise.resolve({ data, message: 'success' }) }
}

function makePayload(overrides: Partial<TodayActionsPayload> = {}): TodayActionsPayload {
  return {
    asOfDate: '2026-04-24',
    mustAct: [],
    monitor: [],
    noAction: [],
    ...overrides,
  }
}

function makeItem(overrides: Partial<ActionItem> = {}): ActionItem {
  return {
    ticker: 'AAPL',
    actionType: 'raise_stop',
    rationale: 'Stop is well below breakeven, raise to protect gains.',
    refs: { positionId: 1, rMultiple: 2.1 },
    ...overrides,
  }
}

// ── A1: GET /api/cockpit/actions/today, no query string ───────────────────────

describe('A1 – getTodayActions URL', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(makePayload())))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('calls GET /api/cockpit/actions/today with no query string', async () => {
    await getTodayActions()
    expect(global.fetch).toHaveBeenCalledWith('/api/cockpit/actions/today', undefined)
  })
})

// ── A2: response剥壳 → returns data portion ───────────────────────────────────

describe('A2 – response unwrapping', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeOkResponse(makePayload({
          asOfDate: '2026-04-24',
          mustAct: [makeItem({ ticker: 'AAPL', actionType: 'raise_stop' })],
          monitor: [makeItem({ ticker: 'TSLA', actionType: 'approaching_trigger' })],
          noAction: [makeItem({ ticker: 'NVDA', actionType: 'stable_position' })],
        })),
      ),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('returns data portion with asOfDate, mustAct, monitor, noAction', async () => {
    const result = await getTodayActions()
    expect(result.asOfDate).toBe('2026-04-24')
    expect(result.mustAct).toHaveLength(1)
    expect(result.mustAct[0].ticker).toBe('AAPL')
    expect(result.monitor).toHaveLength(1)
    expect(result.monitor[0].ticker).toBe('TSLA')
    expect(result.noAction).toHaveLength(1)
    expect(result.noAction[0].ticker).toBe('NVDA')
  })
})

// ── A3: all-empty arrays scenario ─────────────────────────────────────────────

describe('A3 – empty arrays', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(makePayload())))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('mustAct=[] / monitor=[] / noAction=[] does not throw', async () => {
    const result = await getTodayActions()
    expect(result.mustAct).toEqual([])
    expect(result.monitor).toEqual([])
    expect(result.noAction).toEqual([])
    expect(result.asOfDate).toBe('2026-04-24')
  })
})

// ── A4: camelCase field names ─────────────────────────────────────────────────

describe('A4 – camelCase fields', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeOkResponse(makePayload({
          mustAct: [makeItem({ actionType: 'cancel_order' })],
        })),
      ),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('result has camelCase keys, not snake_case', async () => {
    const result = await getTodayActions()
    expect(result).toHaveProperty('asOfDate')
    expect(result).toHaveProperty('mustAct')
    expect(result).toHaveProperty('noAction')
    expect(result.mustAct[0]).toHaveProperty('actionType')
    expect(result).not.toHaveProperty('as_of_date')
    expect(result).not.toHaveProperty('must_act')
    expect(result).not.toHaveProperty('no_action')
    expect(result.mustAct[0]).not.toHaveProperty('action_type')
  })
})

// ── A5: all 6 actionType enum values deserialise correctly ────────────────────

describe('A5 – actionType 6-enum round-trip', () => {
  afterEach(() => vi.unstubAllGlobals())

  const allTypes = [
    'raise_stop',
    'cancel_order',
    'reduce_before_earnings',
    'tighten_stop',
    'approaching_trigger',
    'stable_position',
  ] as const

  it.each(allTypes)('actionType=%s round-trips unchanged', async (actionType) => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeOkResponse(makePayload({ mustAct: [makeItem({ actionType })] }))),
    )
    const result = await getTodayActions()
    expect(result.mustAct[0].actionType).toBe(actionType)
  })
})
