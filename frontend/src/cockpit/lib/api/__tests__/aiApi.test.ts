import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { callAiTask } from '../aiApi'

const mockMeta = {
  modelUsed: 'claude-3-haiku',
  tier: 'haiku',
  tokensIn: 500,
  tokensOut: 200,
  costUsd: 0.001,
  latencyMs: 1200,
  cacheHit: false,
}

const mockOutput = {
  headline: 'Market holding constructive posture',
  summary: 'Breadth improving, tech leading.',
  riskPosture: 'balanced',
  preferredSetups: ['BREAKOUT'],
  avoid: ['SHORT'],
  warnings: [],
}

const mockSuccessResponse = {
  ok: true,
  status: 200,
  json: () =>
    Promise.resolve({
      data: {
        memoId: 42,
        taskType: 'market_narrator',
        schemaVersion: '1.0',
        output: mockOutput,
        meta: mockMeta,
      },
    }),
}

const mockInput = {
  regime: 'CONSTRUCTIVE' as const,
  marketScore: 68,
  subscores: {
    spyTrend: 18,
    qqqTrend: 14,
    iwmBreadth: 9,
    sectorParticipation: 14,
    riskAppetite: 7,
    volatilityStress: 6,
  },
  sectors: [{ symbol: 'XLK', closePct: 0.52, state: 'Strong' as const }],
}

describe('§A – aiApi.callAiTask', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('A1: success → fetch POSTs /api/ai/market_narrator with input + noCache: false', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockSuccessResponse))
    await callAiTask('market_narrator', mockInput)
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/ai/market_narrator')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    expect(body.noCache).toBe(false)
    expect(body.input).toMatchObject({ regime: 'CONSTRUCTIVE', marketScore: 68 })
  })

  it('A2: noCache: true → body.noCache === true', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockSuccessResponse))
    await callAiTask('market_narrator', mockInput, { noCache: true })
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    const body = JSON.parse(init.body as string)
    expect(body.noCache).toBe(true)
  })

  it('A3: returns full response shape (memoId / taskType / schemaVersion / output / meta)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockSuccessResponse))
    const result = await callAiTask('market_narrator', mockInput)
    expect(result.memoId).toBe(42)
    expect(result.taskType).toBe('market_narrator')
    expect(result.schemaVersion).toBe('1.0')
    expect(result.output).toMatchObject(mockOutput)
    expect(result.meta).toMatchObject(mockMeta)
  })

  it('A4: 502 AI_PROVIDER_ERROR → throws ApiError(code="AI_PROVIDER_ERROR", status=502)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: () =>
          Promise.resolve({ error: { code: 'AI_PROVIDER_ERROR', message: 'LLM unavailable' } }),
      }),
    )
    await expect(callAiTask('market_narrator', mockInput)).rejects.toMatchObject({
      code: 'AI_PROVIDER_ERROR',
      status: 502,
    })
  })

  it('A5: 429 AI_BUDGET_EXCEEDED → throws ApiError(code="AI_BUDGET_EXCEEDED", status=429)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
        json: () =>
          Promise.resolve({
            error: { code: 'AI_BUDGET_EXCEEDED', message: 'Monthly budget exceeded' },
          }),
      }),
    )
    await expect(callAiTask('market_narrator', mockInput)).rejects.toMatchObject({
      code: 'AI_BUDGET_EXCEEDED',
      status: 429,
    })
  })

  it('A6: 422 VALIDATION_ERROR → throws ApiError(code="VALIDATION_ERROR", status=422)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: () =>
          Promise.resolve({ error: { code: 'VALIDATION_ERROR', message: 'Invalid input' } }),
      }),
    )
    await expect(callAiTask('market_narrator', mockInput)).rejects.toMatchObject({
      code: 'VALIDATION_ERROR',
      status: 422,
    })
  })

  it('A7: network error (fetch reject) → throws Error (not ApiError)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network failure')))
    await expect(callAiTask('market_narrator', mockInput)).rejects.toThrow('Network failure')
  })
})
