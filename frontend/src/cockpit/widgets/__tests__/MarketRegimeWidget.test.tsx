import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { COCKPIT_WIDGET_REGISTRY, getCockpitDefaultLayout } from '../../CockpitRegistry'
import { MarketRegimeWidget } from '../MarketRegimeWidget'

// ─── S11 / S12 – CockpitRegistry ──────────────────────────────────────────

describe('S11 – CockpitRegistry manifest', () => {
  it('cockpit.market-regime entry exists with correct shape', () => {
    const manifest = COCKPIT_WIDGET_REGISTRY['cockpit.market-regime']
    expect(manifest).toBeDefined()
    expect(manifest.id).toBe('cockpit.market-regime')
    expect(manifest.title).toBe('Market Regime')
    expect(manifest.component).toBe(MarketRegimeWidget)
    expect(manifest.category).toBe('regime')
    expect(manifest.defaultLayout).toMatchObject({ x: 0, y: 0, w: 12, h: 8, minW: 3, minH: 4 })
  })

  it('cockpit.placeholder is NOT in registry', () => {
    expect(COCKPIT_WIDGET_REGISTRY['cockpit.placeholder']).toBeUndefined()
  })
})

describe('S12 – getCockpitDefaultLayout', () => {
  it('contains cockpit.market-regime item', () => {
    const layout = getCockpitDefaultLayout()
    expect(layout.some((item) => item.i === 'cockpit.market-regime')).toBe(true)
  })

  it('does NOT contain cockpit.placeholder item', () => {
    const layout = getCockpitDefaultLayout()
    expect(layout.some((item) => item.i === 'cockpit.placeholder')).toBe(false)
  })
})

// ─── Helpers ──────────────────────────────────────────────────────────────

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

function renderWidget() {
  const client = makeClient()
  return render(
    <QueryClientProvider client={client}>
      <MarketRegimeWidget />
    </QueryClientProvider>,
  )
}

type FetchResponse = { ok: boolean; status: number; json: () => Promise<unknown> }

/**
 * Routes fetch mocks by URL substring.
 * Unmatched URLs get a never-resolving promise (component stays loading).
 */
function makeRoutedFetch(routes: Record<string, () => Promise<FetchResponse>>) {
  return vi.fn().mockImplementation((url: string) => {
    for (const [pattern, handler] of Object.entries(routes)) {
      if (url.includes(pattern)) return handler()
    }
    return new Promise(() => {})
  })
}

const REGIME_OK_FETCH = () =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ data: REGIME_OK }),
  } as FetchResponse)

const REGIME_OK = {
  date: '2026-04-24',
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
  allowedExposurePct: 70.0,
  singleTradeRiskPct: 1.0,
  preferredSetups: ['BREAKOUT', 'CAPITULATION'] as const,
  avoidSetups: ['EXTENDED'] as const,
  indices: [
    { symbol: 'SPY', close: 520.5, changePct: 0.43, aboveMa50: true, aboveMa200: true, rsTrend: 'up' as const, state: 'Bullish' as const },
    { symbol: 'QQQ', close: 450.2, changePct: 0.62, aboveMa50: true, aboveMa200: true, rsTrend: 'up' as const, state: 'Leading' as const },
    { symbol: 'IWM', close: 210.1, changePct: -0.15, aboveMa50: false, aboveMa200: true, rsTrend: 'down' as const, state: 'Weak' as const },
  ],
  sectors: [
    { symbol: 'XLK', close: 210.1, changePct: 0.52, state: 'Strong' as const },
    { symbol: 'XLY', close: 180.3, changePct: 0.31, state: 'Constructive' as const },
    { symbol: 'XLF', close: 42.1, changePct: -0.1, state: 'Weak' as const },
    { symbol: 'XLI', close: 115.0, changePct: 0.2, state: 'Constructive' as const },
    { symbol: 'XLE', close: 88.5, changePct: -0.5, state: 'Defensive' as const },
    { symbol: 'XLV', close: 145.3, changePct: -0.2, state: 'Weak' as const },
    { symbol: 'XLC', close: 93.0, changePct: 0.7, state: 'Strong' as const },
    { symbol: 'XLP', close: null, changePct: null, state: 'Neutral' as const },
    { symbol: 'XLU', close: 68.0, changePct: -0.3, state: 'Neutral' as const },
    { symbol: 'XLB', close: 88.0, changePct: 0.4, state: 'Constructive' as const },
    { symbol: 'XLRE', close: 40.0, changePct: -0.1, state: 'Weak' as const },
  ],
  computedAt: '2026-04-24T22:05:00Z',
}

// ─── S3 – Score Hero normal state ─────────────────────────────────────────

describe('S3 – Score Hero normal state', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ '/cockpit/regime': REGIME_OK_FETCH }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders regime pill text', async () => {
    renderWidget()
    expect(await screen.findByText('CONSTRUCTIVE')).toBeInTheDocument()
  })

  it('renders market score', async () => {
    renderWidget()
    expect(await screen.findByText('68 / 100')).toBeInTheDocument()
  })

  it('renders Allowed Exposure and Single Trade Risk (toFixed(2) precision)', async () => {
    renderWidget()
    expect(await screen.findByText(/70\.0%/)).toBeInTheDocument()
    expect(await screen.findByText(/1\.00%/)).toBeInTheDocument()
  })
})

// ─── S4 – 6-dim Subscores ─────────────────────────────────────────────────

describe('S4 – 6-dim Subscores', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ '/cockpit/regime': REGIME_OK_FETCH }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders 6 subscore cards', async () => {
    renderWidget()
    // unique values
    expect(await screen.findByText('18 / 25')).toBeInTheDocument()
    expect(await screen.findByText('9 / 15')).toBeInTheDocument()
    expect(await screen.findByText('7 / 10')).toBeInTheDocument()
    expect(await screen.findByText('6 / 10')).toBeInTheDocument()
    // '14 / 20' appears twice (qqqTrend=14 and sectorParticipation=14)
    const fourteenCells = screen.getAllByText('14 / 20')
    expect(fourteenCells).toHaveLength(2)
  })
})

// ─── S5 – Indices Card ────────────────────────────────────────────────────

describe('S5 – Indices Card', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ '/cockpit/regime': REGIME_OK_FETCH }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders 3 index rows', async () => {
    renderWidget()
    expect(await screen.findByText('SPY')).toBeInTheDocument()
    expect(await screen.findByText('QQQ')).toBeInTheDocument()
    expect(await screen.findByText('IWM')).toBeInTheDocument()
  })

  it('renders close price formatted', async () => {
    renderWidget()
    expect(await screen.findByText('$520.50')).toBeInTheDocument()
  })

  it('renders positive changePct in green-tinted text', async () => {
    renderWidget()
    expect(await screen.findByText('+0.43%')).toBeInTheDocument()
  })

  it('renders negative changePct', async () => {
    renderWidget()
    expect(await screen.findByText('-0.15%')).toBeInTheDocument()
  })

  it('renders state labels', async () => {
    renderWidget()
    expect(await screen.findByText('Bullish')).toBeInTheDocument()
    expect(await screen.findByText('Leading')).toBeInTheDocument()
    expect(await screen.findByText('Weak')).toBeInTheDocument()
  })
})

// ─── S6 – Sector Heatmap ──────────────────────────────────────────────────

describe('S6 – Sector Heatmap', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ '/cockpit/regime': REGIME_OK_FETCH }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders all 11 sector symbols', async () => {
    renderWidget()
    for (const sym of ['XLK', 'XLY', 'XLF', 'XLI', 'XLE', 'XLV', 'XLC', 'XLP', 'XLU', 'XLB', 'XLRE']) {
      expect(await screen.findByText(sym)).toBeInTheDocument()
    }
  })
})

// ─── S7 – Sector close=null → "—" ─────────────────────────────────────────

describe('S7 – Sector null data fallback', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ '/cockpit/regime': REGIME_OK_FETCH }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('XLP with close=null renders "—"', async () => {
    renderWidget()
    await screen.findByText('XLP')
    expect(screen.getByTestId('sector-XLP-close')).toHaveTextContent('—')
  })
})

// ─── S8 – Loading skeleton ─────────────────────────────────────────────────

describe('S8 – Loading skeleton', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows skeleton while loading', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise(() => {})),
    )
    renderWidget()
    const skeletons = document.querySelectorAll('[data-testid="skeleton"]')
    expect(skeletons.length).toBeGreaterThan(0)
  })
})

// ─── S9 – 404 EmptyState ──────────────────────────────────────────────────

describe('S9 – 404 EmptyState', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: { code: 'NOT_FOUND', message: 'no snapshot' } }),
      }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders EmptyState text on 404', async () => {
    renderWidget()
    expect(await screen.findByText(/首日 regime 计算中/)).toBeInTheDocument()
  })

  it('no [手动触发] button (D2)', async () => {
    renderWidget()
    await screen.findByText(/首日 regime 计算中/)
    expect(screen.queryByRole('button', { name: /手动触发/ })).toBeNull()
  })
})

// ─── S10 – 502 error state ────────────────────────────────────────────────

describe('S10 – 502 error state', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: () => Promise.resolve({}),
      }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders retry button on 502', async () => {
    renderWidget()
    expect(await screen.findByRole('button', { name: /加载失败|重试/ })).toBeInTheDocument()
  })
})

// ─── AI mock fixtures ─────────────────────────────────────────────────────

const AI_SUCCESS_DATA = {
  memoId: 42,
  taskType: 'market_narrator',
  schemaVersion: '1.0',
  output: {
    headline: 'Market holding constructive posture',
    summary: 'Breadth improving, tech leading.',
    riskPosture: 'balanced',
    preferredSetups: ['BREAKOUT'],
    avoid: ['SHORT'],
    warnings: ['Elevated volatility detected'],
  },
  meta: {
    modelUsed: 'claude-3-haiku',
    tier: 'haiku',
    tokensIn: 500,
    tokensOut: 200,
    costUsd: 0.001,
    latencyMs: 1200,
    cacheHit: false,
  },
}

const AI_SUCCESS_FETCH = () =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ data: AI_SUCCESS_DATA }),
  } as FetchResponse)

const AI_502_FETCH = () =>
  Promise.resolve({
    ok: false,
    status: 502,
    json: () => Promise.resolve({ error: { code: 'AI_PROVIDER_ERROR', message: 'LLM down' } }),
  } as FetchResponse)

const AI_429_FETCH = () =>
  Promise.resolve({
    ok: false,
    status: 429,
    json: () =>
      Promise.resolve({ error: { code: 'AI_BUDGET_EXCEEDED', message: 'Budget exceeded' } }),
  } as FetchResponse)

// ─── S13 – no console errors ──────────────────────────────────────────────

describe('S13 – no console errors on normal render', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ '/cockpit/regime': REGIME_OK_FETCH }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('no console.error during render', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderWidget()
    await screen.findByText('CONSTRUCTIVE')
    expect(errorSpy).not.toHaveBeenCalled()
    errorSpy.mockRestore()
  })
})

// ─── S14 – AI Market Notes integration ───────────────────────────────────

describe('S14 – AI Market Notes integration', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('S14.1: regime 200 + AI 200 → renders headline / summary / warnings', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ '/cockpit/regime': REGIME_OK_FETCH, '/ai/': AI_SUCCESS_FETCH }),
    )
    renderWidget()
    expect(await screen.findByText('Market holding constructive posture')).toBeInTheDocument()
    expect(await screen.findByText(/Breadth improving/)).toBeInTheDocument()
    expect(await screen.findByText(/Elevated volatility detected/)).toBeInTheDocument()
  })

  it('S14.2: AI 502 → upper 4 blocks normal + AI area "AI 暂不可用"', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ '/cockpit/regime': REGIME_OK_FETCH, '/ai/': AI_502_FETCH }),
    )
    renderWidget()
    expect(await screen.findByText('CONSTRUCTIVE')).toBeInTheDocument()
    expect(await screen.findByText('AI 暂不可用')).toBeInTheDocument()
  })

  it('S14.3: AI 429 BUDGET_EXCEEDED → "AI 暂不可用" + Refresh disabled', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ '/cockpit/regime': REGIME_OK_FETCH, '/ai/': AI_429_FETCH }),
    )
    renderWidget()
    await screen.findByText('AI 暂不可用')
    const refreshBtn = screen.getByRole('button', { name: /Refresh/ })
    expect(refreshBtn).toBeDisabled()
  })

  it('S14.4: successful AI fetch → Refresh button stays enabled (cooldown removed)', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ '/cockpit/regime': REGIME_OK_FETCH, '/ai/': AI_SUCCESS_FETCH }),
    )
    renderWidget()
    await screen.findByText('Market holding constructive posture')
    const refreshBtn = screen.getByRole('button', { name: /Refresh/ })
    expect(refreshBtn).not.toBeDisabled()
  })

  it('S14.5: Refresh click sends noCache: true in request body', async () => {
    const fetchMock = makeRoutedFetch({
      '/cockpit/regime': REGIME_OK_FETCH,
      '/ai/': AI_502_FETCH,
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await screen.findByText('AI 暂不可用')

    const refreshBtn = screen.getByRole('button', { name: /Refresh/ })
    fireEvent.click(refreshBtn)

    await waitFor(() => {
      const aiCalls = fetchMock.mock.calls.filter(([url]) =>
        (url as string).includes('/ai/'),
      )
      expect(aiCalls.length).toBeGreaterThanOrEqual(2)
    })

    const aiCalls = fetchMock.mock.calls.filter(([url]) => (url as string).includes('/ai/'))
    const lastBody = JSON.parse(aiCalls[aiCalls.length - 1][1].body as string)
    expect(lastBody.noCache).toBe(true)
  })

  it('S14.6: sector normalization — Constructive/Defensive map to Strong/Weak in AI request', async () => {
    const fetchMock = makeRoutedFetch({
      '/cockpit/regime': REGIME_OK_FETCH,
      '/ai/': AI_SUCCESS_FETCH,
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await screen.findByText('Market holding constructive posture')

    const aiCalls = fetchMock.mock.calls.filter(([url]) => (url as string).includes('/ai/'))
    expect(aiCalls.length).toBeGreaterThan(0)
    const body = JSON.parse(aiCalls[0][1].body as string)
    const sectorStates: string[] = body.input.sectors.map(
      (s: { state: string }) => s.state,
    )
    expect(sectorStates).not.toContain('Constructive')
    expect(sectorStates).not.toContain('Defensive')
    // REGIME_OK: XLY=Constructive→Strong, XLE=Defensive→Weak
    const xly = body.input.sectors.find((s: { symbol: string }) => s.symbol === 'XLY')
    expect(xly.state).toBe('Strong')
    const xle = body.input.sectors.find((s: { symbol: string }) => s.symbol === 'XLE')
    expect(xle.state).toBe('Weak')
  })
})

// ── S9 (F215-a): toFixed(2) precision for Risk/Trade ─────────────────────────

describe('S9 (F215-a) – singleTradeRiskPct toFixed(2) precision', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('RISK_ON 1.25 displays as "1.25%"', async () => {
    const riskOnData = {
      ...REGIME_OK,
      regime: 'RISK_ON' as const,
      singleTradeRiskPct: 1.25,
    }
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/regime': () =>
          Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve({ data: riskOnData }),
          } as { ok: boolean; status: number; json: () => Promise<unknown> }),
      }),
    )
    renderWidget()
    expect(await screen.findByText(/1\.25%/)).toBeInTheDocument()
  })

  it('other regimes also show 2 decimal places (0.75%, 1.00%, 0.50%)', async () => {
    const cases: Array<[number, RegExp]> = [
      [0.75, /0\.75%/],
      [1.0, /1\.00%/],
      [0.5, /0\.50%/],
    ]
    for (const [value, pattern] of cases) {
      vi.unstubAllGlobals()
      vi.stubGlobal(
        'fetch',
        makeRoutedFetch({
          '/cockpit/regime': () =>
            Promise.resolve({
              ok: true,
              status: 200,
              json: () => Promise.resolve({ data: { ...REGIME_OK, singleTradeRiskPct: value } }),
            } as { ok: boolean; status: number; json: () => Promise<unknown> }),
        }),
      )
      const { unmount } = renderWidget()
      expect(await screen.findByText(pattern)).toBeInTheDocument()
      unmount()
    }
  })
})
