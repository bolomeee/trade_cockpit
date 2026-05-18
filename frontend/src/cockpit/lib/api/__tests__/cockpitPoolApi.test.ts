import { describe, it, expect, vi, afterEach } from 'vitest'
import { getCockpitPool, POOL_TIMEOUT_MS } from '../cockpitPoolApi'

type MockResponse = { ok: boolean; status: number; json: () => Promise<unknown> }

function makeOkResponse(data: unknown): MockResponse {
  return { ok: true, status: 200, json: () => Promise.resolve({ data, message: 'success' }) }
}

function makeErrResponse(status: number): MockResponse {
  return { ok: false, status, json: () => Promise.resolve({ error: { code: 'ERR', message: 'error' } }) }
}

const EMPTY_POOL = {
  funnel: { tradable: 0, trend: 0, rs: 0, fundamental: 0, action: 0 },
  items: [],
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('S1 – empty filters → no query string', () => {
  it('GET /api/cockpit/pool with no params', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(EMPTY_POOL)))
    await getCockpitPool({})
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/cockpit/pool')
  })
})

describe('S2 – multiple filters with sectors comma-separated', () => {
  it('URL contains all params; sectors and setupTypes are URL-encoded commas', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(EMPTY_POOL)))
    await getCockpitPool({
      trendScoreMin: 4,
      rsPercentileMin: 80,
      sectors: 'XLK,XLV',
      setupTypes: 'BREAKOUT,CAPITULATION',
      limit: 25,
    })
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toContain('trendScoreMin=4')
    expect(url).toContain('rsPercentileMin=80')
    expect(url).toContain('sectors=XLK%2CXLV')
    expect(url).toContain('setupTypes=BREAKOUT%2CCAPITULATION')
    expect(url).toContain('limit=25')
  })
})

describe('S3 – 60s timeout via AbortSignal', () => {
  it('AbortSignal fires exactly at POOL_TIMEOUT_MS', () => {
    vi.useFakeTimers()
    let capturedSignal: AbortSignal | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
        capturedSignal = init?.signal
        return new Promise(() => {})
      }),
    )
    getCockpitPool({})
    expect(capturedSignal?.aborted).toBe(false)
    vi.advanceTimersByTime(POOL_TIMEOUT_MS)
    expect(capturedSignal?.aborted).toBe(true)
  })
})

describe('S4 – error response throws', () => {
  it('5xx response rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeErrResponse(500)))
    await expect(getCockpitPool({})).rejects.toThrow()
  })

  it('4xx response rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeErrResponse(422)))
    await expect(getCockpitPool({})).rejects.toThrow()
  })
})
