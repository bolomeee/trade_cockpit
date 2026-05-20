import { describe, it, expect, vi, afterEach } from 'vitest'
import {
  getTickerRepricingTriggers,
  getAllActiveTriggers,
  type RepricingTrigger,
  type EarningsAccelEvidence,
  type MarginExpansionEvidence,
} from '../cockpitRepricingApi'
import { ApiError } from '@/lib/api/client'

type MockResponse = { ok: boolean; status: number; json: () => Promise<unknown> }

function makeOkResponse(data: unknown): MockResponse {
  return { ok: true, status: 200, json: () => Promise.resolve({ data, message: 'success' }) }
}

function makeErrResponse(status: number): MockResponse {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({ error: { code: 'ERR', message: 'error' } }),
  }
}

const TICKER_PAYLOAD = {
  ticker: 'NVDA',
  triggers: [],
}

const EMPTY_ALL_PAYLOAD = {
  triggers: [],
  totalCount: 0,
  computedAt: '2026-05-20T22:40:00Z',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('A1 – getTickerRepricingTriggers uppercases ticker', () => {
  it('calls /api/cockpit/repricing-triggers/NVDA from lowercase "nvda"', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(TICKER_PAYLOAD)))
    await getTickerRepricingTriggers('nvda')
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/cockpit/repricing-triggers/NVDA')
  })
})

describe('A2 – getAllActiveTriggers no params → no query string', () => {
  it('calls /api/cockpit/repricing-triggers without trailing "?"', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(EMPTY_ALL_PAYLOAD)))
    await getAllActiveTriggers()
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/cockpit/repricing-triggers')
  })
})

describe('A3 – getAllActiveTriggers with params → query string present', () => {
  it('URL contains triggerType=MARGIN_EXPANSION and limit=50', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(EMPTY_ALL_PAYLOAD)))
    await getAllActiveTriggers({ triggerType: 'MARGIN_EXPANSION', limit: 50 })
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toContain('triggerType=MARGIN_EXPANSION')
    expect(url).toContain('limit=50')
  })
})

describe('A4 – empty triggers + totalCount=0 → no error', () => {
  it('returns empty payload structure without throwing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(EMPTY_ALL_PAYLOAD)))
    const result = await getAllActiveTriggers()
    expect(result.triggers).toHaveLength(0)
    expect(result.totalCount).toBe(0)
  })
})

describe('A5 – 422 response → throws ApiError with status 422', () => {
  it('rejects with ApiError, .status === 422', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeErrResponse(422)))
    const err = await getAllActiveTriggers().catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(422)
  })
})

describe('A6 – TypeScript evidence union narrow via switch on triggerType', () => {
  it('accesses type-specific evidence fields after switch without any', () => {
    function summarize(t: RepricingTrigger): string {
      switch (t.triggerType) {
        case 'EARNINGS_ACCEL': {
          const ev = t.evidence as EarningsAccelEvidence
          return `eps yoy ${ev.epsYoyGrowth.at(-1)}%`
        }
        case 'MARGIN_EXPANSION': {
          const ev = t.evidence as MarginExpansionEvidence
          return `${ev.triggerMetric} +${ev.expansionBp}bp`
        }
        default:
          return 'other'
      }
    }

    const trigger: RepricingTrigger = {
      triggerType: 'EARNINGS_ACCEL',
      detectedDate: '2026-05-15',
      confidence: 0.8,
      evidence: { epsYoyGrowth: [78], revenueYoyGrowth: [32], quarters: ['Q1-2026'] },
      computedAt: '2026-05-20T22:40:00Z',
    }
    expect(summarize(trigger)).toBe('eps yoy 78%')

    const marginTrigger: RepricingTrigger = {
      triggerType: 'MARGIN_EXPANSION',
      detectedDate: '2026-05-15',
      confidence: 0.75,
      evidence: {
        grossMarginTrend: [0.40, 0.49],
        fcfMarginTrend: [0.10, 0.15],
        quarters: ['Q4-2025', 'Q1-2026'],
        triggerMetric: 'gross_margin',
        expansionBp: 900,
      },
      computedAt: '2026-05-20T22:40:00Z',
    }
    expect(summarize(marginTrigger)).toBe('gross_margin +900bp')
  })
})
