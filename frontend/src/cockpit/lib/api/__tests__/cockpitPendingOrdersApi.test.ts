import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  getPendingOrders,
  createPendingOrder,
  updatePendingOrder,
  deletePendingOrder,
} from '../cockpitPendingOrdersApi'

const mockOrder = {
  id: 1,
  ticker: 'NVDA',
  setupType: 'BREAKOUT',
  entryPrice: 900.0,
  stopPrice: 860.0,
  shares: 20,
  target2r: 980.0,
  target3r: 1020.0,
  expirationDate: '2026-05-30',
  status: 'ACTIVE',
  lastClose: 870.0,
  distanceToTriggerPct: 3.45,
  riskPct: 1.5,
  notes: 'test note',
  createdAt: '2026-04-20T10:00:00Z',
  updatedAt: '2026-04-20T10:00:00Z',
}

function makeOkResponse(data: unknown, status = 200) {
  return { ok: true, status, json: () => Promise.resolve({ data, message: 'success' }) }
}

// ── S1 getPendingOrders ───────────────────────────────────────────────────────

describe('S1 – getPendingOrders', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse([mockOrder])))
  })
  afterEach(() => vi.unstubAllGlobals())

  it("status='active' → GET /api/cockpit/pending-orders?status=active", async () => {
    await getPendingOrders('active')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/cockpit/pending-orders?status=active',
      undefined,
    )
  })

  it("status='all' → URL contains status=all", async () => {
    await getPendingOrders('all')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/cockpit/pending-orders?status=all',
      undefined,
    )
  })

  it("status='triggered' → URL contains status=triggered", async () => {
    await getPendingOrders('triggered')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/cockpit/pending-orders?status=triggered',
      undefined,
    )
  })

  it('response returns PendingOrder array with all fields', async () => {
    const result = await getPendingOrders('active')
    expect(result).toHaveLength(1)
    expect(result[0].ticker).toBe('NVDA')
    expect(result[0].distanceToTriggerPct).toBe(3.45)
    expect(result[0].riskPct).toBe(1.5)
    expect(result[0].status).toBe('ACTIVE')
    expect(result[0].expirationDate).toBe('2026-05-30')
  })
})

// ── S2 createPendingOrder ─────────────────────────────────────────────────────

describe('S2 – createPendingOrder', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(mockOrder, 201)))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('POST to /api/cockpit/pending-orders', async () => {
    await createPendingOrder({ ticker: 'NVDA', entryPrice: 900, stopPrice: 860, shares: 20 })
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/cockpit/pending-orders')
    expect(init.method).toBe('POST')
  })

  it('body fields are camelCase', async () => {
    await createPendingOrder({
      ticker: 'NVDA',
      setupType: 'BREAKOUT',
      entryPrice: 900,
      stopPrice: 860,
      shares: 20,
      target2r: 980,
      target3r: 1020,
      expirationDate: '2026-05-30',
      notes: 'test',
    })
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body)
    expect(body.entryPrice).toBe(900)
    expect(body.stopPrice).toBe(860)
    expect(body.setupType).toBe('BREAKOUT')
    expect(body.target2r).toBe(980)
    expect(body.expirationDate).toBe('2026-05-30')
    expect(body).not.toHaveProperty('entry_price')
    expect(body).not.toHaveProperty('stop_price')
  })

  it('returns PendingOrder object', async () => {
    const result = await createPendingOrder({ ticker: 'NVDA', entryPrice: 900, stopPrice: 860, shares: 20 })
    expect(result.id).toBe(1)
    expect(result.ticker).toBe('NVDA')
    expect(result.status).toBe('ACTIVE')
  })
})

// ── S3 updatePendingOrder ─────────────────────────────────────────────────────

describe('S3 – updatePendingOrder', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeOkResponse({ ...mockOrder, stopPrice: 870 })),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('PATCH to /api/cockpit/pending-orders/{id}', async () => {
    await updatePendingOrder(1, { stopPrice: 870 })
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/cockpit/pending-orders/1')
    expect(init.method).toBe('PATCH')
  })

  it('only provided patch fields appear in body', async () => {
    await updatePendingOrder(1, { stopPrice: 870 })
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body)
    expect(body.stopPrice).toBe(870)
    expect(body).not.toHaveProperty('ticker')
    expect(body).not.toHaveProperty('status')
    expect(body).not.toHaveProperty('entryPrice')
    expect(body).not.toHaveProperty('notes')
  })

  it('status-only patch for Triggered flow', async () => {
    await updatePendingOrder(1, { status: 'TRIGGERED' })
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body)
    expect(body.status).toBe('TRIGGERED')
    expect(Object.keys(body)).toHaveLength(1)
  })

  it('status-only patch for Cancel flow', async () => {
    await updatePendingOrder(2, { status: 'CANCELLED' })
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body)
    expect(body.status).toBe('CANCELLED')
    expect(Object.keys(body)).toHaveLength(1)
  })

  it('multi-field patch carries all provided fields', async () => {
    await updatePendingOrder(1, { stopPrice: 870, notes: 'updated', expirationDate: '2026-06-01' })
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body)
    expect(body.stopPrice).toBe(870)
    expect(body.notes).toBe('updated')
    expect(body.expirationDate).toBe('2026-06-01')
  })
})

// ── S4 deletePendingOrder ─────────────────────────────────────────────────────

describe('S4 – deletePendingOrder', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse({ id: 1, deleted: true })))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('DELETE to /api/cockpit/pending-orders/{id}', async () => {
    await deletePendingOrder(1)
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/cockpit/pending-orders/1')
    expect(init.method).toBe('DELETE')
  })

  it('returns { id, deleted }', async () => {
    const result = await deletePendingOrder(1)
    expect(result.id).toBe(1)
    expect(result.deleted).toBe(true)
  })
})
