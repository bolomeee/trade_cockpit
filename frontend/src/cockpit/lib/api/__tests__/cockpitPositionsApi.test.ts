import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getPositions, createPosition, updatePosition, deletePosition } from '../cockpitPositionsApi'

const mockPosition = {
  id: 1,
  ticker: 'NVDA',
  entryPrice: 850.0,
  entryDate: '2026-04-15',
  shares: 33,
  stopPrice: 820.0,
  target2r: 910.0,
  target3r: 940.0,
  setupType: 'BREAKOUT',
  status: 'OPEN',
  lastClose: 875.0,
  rMultiple: 0.83,
  unrealizedPl: 825.0,
  positionValue: 28875.0,
  earningsDate: '2026-05-22',
  daysUntilEarnings: 28,
  nextAction: 'hold',
  closedAt: null,
  closePrice: null,
  notes: null,
  createdAt: '2026-04-15T10:00:00Z',
  updatedAt: '2026-04-15T10:00:00Z',
}

const mockSummary = {
  openRiskPct: 2.5,
  totalExposurePct: 45.0,
  pendingRiskPct: 1.0,
  positionsCount: 5,
  pendingCount: 2,
}

function makeOkResponse(data: unknown, status = 200) {
  return { ok: true, status, json: () => Promise.resolve({ data, message: 'success' }) }
}

describe('S1 – getPositions', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeOkResponse({ summary: mockSummary, items: [mockPosition] })),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it("status='open' → GET /api/cockpit/positions?status=open", async () => {
    await getPositions('open')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/cockpit/positions?status=open',
      undefined,
    )
  })

  it("status='closed' → URL contains status=closed", async () => {
    await getPositions('closed')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/cockpit/positions?status=closed',
      undefined,
    )
  })

  it("status='all' → URL contains status=all", async () => {
    await getPositions('all')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/cockpit/positions?status=all',
      undefined,
    )
  })

  it('response deserialized into { summary, items }', async () => {
    const result = await getPositions('open')
    expect(result.summary.openRiskPct).toBe(2.5)
    expect(result.summary.positionsCount).toBe(5)
    expect(result.items).toHaveLength(1)
    expect(result.items[0].ticker).toBe('NVDA')
    expect(result.items[0].rMultiple).toBe(0.83)
  })
})

describe('S2 – createPosition', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(mockPosition, 201)))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('POST to /api/cockpit/positions', async () => {
    await createPosition({
      ticker: 'NVDA',
      entryPrice: 850,
      entryDate: '2026-04-15',
      shares: 33,
      stopPrice: 820,
    })
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/cockpit/positions')
    expect(init.method).toBe('POST')
  })

  it('body fields are camelCase', async () => {
    await createPosition({
      ticker: 'NVDA',
      entryPrice: 850,
      entryDate: '2026-04-15',
      shares: 33,
      stopPrice: 820,
      target2r: 910,
      setupType: 'BREAKOUT',
      notes: 'test',
    })
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body)
    expect(body.entryPrice).toBe(850)
    expect(body.entryDate).toBe('2026-04-15')
    expect(body.stopPrice).toBe(820)
    expect(body.target2r).toBe(910)
    expect(body.setupType).toBe('BREAKOUT')
    expect(body).not.toHaveProperty('entry_price')
  })

  it('returns Position object', async () => {
    const result = await createPosition({
      ticker: 'NVDA',
      entryPrice: 850,
      entryDate: '2026-04-15',
      shares: 33,
      stopPrice: 820,
    })
    expect(result.id).toBe(1)
    expect(result.ticker).toBe('NVDA')
  })
})

describe('S3 – updatePosition', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeOkResponse({ ...mockPosition, stopPrice: 840 })),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('PATCH to /api/cockpit/positions/{id}', async () => {
    await updatePosition(1, { stopPrice: 840 })
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/cockpit/positions/1')
    expect(init.method).toBe('PATCH')
  })

  it('only provided patch fields appear in body', async () => {
    await updatePosition(1, { stopPrice: 840 })
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body)
    expect(body.stopPrice).toBe(840)
    expect(body).not.toHaveProperty('status')
    expect(body).not.toHaveProperty('closedAt')
    expect(body).not.toHaveProperty('closePrice')
    expect(body).not.toHaveProperty('notes')
  })

  it('all patch fields included when provided', async () => {
    await updatePosition(2, {
      status: 'CLOSED',
      closedAt: '2026-04-30T10:00:00Z',
      closePrice: 900,
      notes: 'hit 2r',
    })
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body)
    expect(body.status).toBe('CLOSED')
    expect(body.closedAt).toBe('2026-04-30T10:00:00Z')
    expect(body.closePrice).toBe(900)
    expect(body.notes).toBe('hit 2r')
  })
})

describe('S4 – deletePosition', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeOkResponse({ id: 1, deleted: true })),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('DELETE to /api/cockpit/positions/{id}', async () => {
    await deletePosition(1)
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/cockpit/positions/1')
    expect(init.method).toBe('DELETE')
  })

  it('returns { id, deleted }', async () => {
    const result = await deletePosition(1)
    expect(result.id).toBe(1)
    expect(result.deleted).toBe(true)
  })
})
