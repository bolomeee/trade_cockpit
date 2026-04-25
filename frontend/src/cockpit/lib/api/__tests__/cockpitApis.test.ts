import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getCockpitChart } from '../cockpitChartApi'
import { getCockpitDecision } from '../cockpitDecisionApi'

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
