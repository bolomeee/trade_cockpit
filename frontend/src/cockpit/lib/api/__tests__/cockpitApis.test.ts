import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getCockpitChart } from '../cockpitChartApi'
import { getCockpitDecision } from '../cockpitDecisionApi'
import { getCockpitRegime } from '../cockpitRegimeApi'
import { getCockpitWeeklyChart } from '../cockpitWeeklyChartApi'

const chartOkResponse = {
  ok: true,
  json: () =>
    Promise.resolve({
      data: {
        ticker: 'NVDA',
        bars: [],
        mas: {},
        atr: [],
        avwap: { anchor: null, series: [] },
      },
    }),
}

const decisionOkResponse = {
  ok: true,
  json: () =>
    Promise.resolve({
      data: {
        ticker: 'NVDA',
        setupType: 'BREAKOUT',
        setupQuality: 'A',
        entryPrice: 850,
        stopPrice: 820,
        target2r: 910,
        target3r: 940,
        rewardRisk: 2,
        riskPerShare: 30,
        suggestedShares: 33,
        positionValue: 28050,
        accountRiskPct: 0.99,
        effectiveRiskPct: 1.0,
        regimeCap: 1.0,
        userSettingCap: 1.0,
        earningsRisk: 'SAFE',
        earningsDate: '2026-05-22',
        deterministicHash: 'abc123',
      },
    }),
}

describe('S1 – cockpitChartApi', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(chartOkResponse))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('default params → correct URL', async () => {
    await getCockpitChart('NVDA')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/cockpit/chart/NVDA?mas=10,21,50,150,200&days=250',
      undefined,
    )
  })

  it('custom mas and days', async () => {
    await getCockpitChart('AAPL', { mas: [10, 50], days: 150 })
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/cockpit/chart/AAPL?mas=10,50&days=150',
      undefined,
    )
  })

  it('anchor param appended when provided', async () => {
    await getCockpitChart('NVDA', { anchor: '2026-01-15' })
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).toContain('anchor=2026-01-15')
  })
})

describe('S2 – cockpitDecisionApi', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(decisionOkResponse))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('no overrides → no extra query params', async () => {
    await getCockpitDecision('NVDA')
    expect(global.fetch).toHaveBeenCalledWith('/api/cockpit/decision/NVDA', undefined)
  })

  it('overrides present → query params included', async () => {
    await getCockpitDecision('NVDA', { entryOverride: 851, riskPctOverride: 0.5 })
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).toContain('entryOverride=851')
    expect(url).toContain('riskPctOverride=0.5')
    expect(url).not.toContain('stopOverride')
  })

  it('omitted override fields not present in URL', async () => {
    await getCockpitDecision('NVDA', { stopOverride: 810 })
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).toContain('stopOverride=810')
    expect(url).not.toContain('entryOverride')
    expect(url).not.toContain('riskPctOverride')
  })
})

const regimeOkResponse = {
  ok: true,
  status: 200,
  json: () =>
    Promise.resolve({
      data: {
        date: '2026-04-24',
        regime: 'CONSTRUCTIVE',
        marketScore: 68,
        subscores: {
          spyTrend: 18,
          qqqTrend: 14,
          iwmBreadth: 9,
          sectorParticipation: 14,
          riskAppetite: 7,
          volatilityStress: 6,
        },
        allowedExposurePct: 70.0,
        singleTradeRiskPct: 1.0,
        preferredSetups: ['BREAKOUT', 'CAPITULATION'],
        avoidSetups: ['EXTENDED'],
        indices: [
          { symbol: 'SPY', close: 520.5, changePct: 0.43, aboveMa50: true, aboveMa200: true, rsTrend: 'up', state: 'Bullish' },
          { symbol: 'QQQ', close: 450.2, changePct: 0.62, aboveMa50: true, aboveMa200: true, rsTrend: 'up', state: 'Leading' },
          { symbol: 'IWM', close: 210.1, changePct: -0.15, aboveMa50: false, aboveMa200: true, rsTrend: 'down', state: 'Weak' },
        ],
        sectors: [
          { symbol: 'XLK', close: 210.1, changePct: 0.52, state: 'Strong' },
          { symbol: 'XLY', close: 180.3, changePct: 0.31, state: 'Constructive' },
          { symbol: 'XLF', close: 42.1, changePct: -0.1, state: 'Weak' },
          { symbol: 'XLI', close: 115.0, changePct: 0.2, state: 'Constructive' },
          { symbol: 'XLE', close: 88.5, changePct: -0.5, state: 'Defensive' },
          { symbol: 'XLV', close: 145.3, changePct: -0.2, state: 'Weak' },
          { symbol: 'XLC', close: 93.0, changePct: 0.7, state: 'Strong' },
          { symbol: 'XLP', close: 76.0, changePct: 0.1, state: 'Neutral' },
          { symbol: 'XLU', close: 68.0, changePct: -0.3, state: 'Neutral' },
          { symbol: 'XLB', close: 88.0, changePct: 0.4, state: 'Constructive' },
          { symbol: 'XLRE', close: 40.0, changePct: -0.1, state: 'Weak' },
        ],
        computedAt: '2026-04-24T22:05:00Z',
      },
    }),
}

describe('S3 – cockpitRegimeApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('OK 200 → calls /api/cockpit/regime and returns CockpitRegimeData', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(regimeOkResponse))
    const result = await getCockpitRegime()
    expect(global.fetch).toHaveBeenCalledWith('/api/cockpit/regime', undefined)
    expect(result.regime).toBe('CONSTRUCTIVE')
    expect(result.marketScore).toBe(68)
    expect(result.subscores.spyTrend).toBe(18)
    expect(result.indices).toHaveLength(3)
    expect(result.sectors).toHaveLength(11)
    expect(result.preferredSetups).toContain('BREAKOUT')
  })

  it('404 → throws ApiError with code NOT_FOUND', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: { code: 'NOT_FOUND', message: 'no snapshot' } }),
      }),
    )
    await expect(getCockpitRegime()).rejects.toMatchObject({ code: 'NOT_FOUND', status: 404 })
  })

  it('502 → throws ApiError with status 502', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: () => Promise.resolve({}),
      }),
    )
    await expect(getCockpitRegime()).rejects.toMatchObject({ status: 502 })
  })
})

const weeklyOkResponse = {
  ok: true,
  status: 200,
  json: () =>
    Promise.resolve({
      data: {
        ticker: 'AAPL',
        weeklyBars: [],
        weeklyMas: { '10': [], '30': [], '40': [] },
        stage: {
          stage: 0,
          weeklyClose: null,
          weeklyMa10: null,
          weeklyMa30: null,
          weeklyMa40: null,
          slope30W: null,
          scanDate: null,
        },
      },
    }),
}

describe('S4 – cockpitWeeklyChartApi', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(weeklyOkResponse))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('default weeks=50 → correct URL', async () => {
    await getCockpitWeeklyChart('AAPL')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/cockpit/chart/AAPL/weekly?weeks=50',
      undefined,
    )
  })

  it('custom weeks=30 → URL contains weeks=30', async () => {
    await getCockpitWeeklyChart('AAPL', { weeks: 30 })
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/cockpit/chart/AAPL/weekly?weeks=30',
      undefined,
    )
  })

  it('404 → throws ApiError with code NOT_FOUND', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: { code: 'NOT_FOUND', message: 'ticker not found' } }),
      }),
    )
    await expect(getCockpitWeeklyChart('UNKNOWN')).rejects.toMatchObject({
      code: 'NOT_FOUND',
      status: 404,
    })
  })

  it('422 → throws ApiError with code VALIDATION_ERROR', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: () =>
          Promise.resolve({ error: { code: 'VALIDATION_ERROR', message: 'weeks out of range' } }),
      }),
    )
    await expect(getCockpitWeeklyChart('AAPL', { weeks: 5 })).rejects.toMatchObject({
      code: 'VALIDATION_ERROR',
      status: 422,
    })
  })
})
