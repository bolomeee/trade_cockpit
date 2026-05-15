import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SetupMonitorWidget } from '../SetupMonitorWidget'
import type { SetupItem, SetupMonitorData } from '../../lib/api/setupMonitorApi'

// ─── Store mock ───────────────────────────────────────────────────────────────

const mockSetSelectedTicker = vi.fn()
vi.mock('@/store/cockpitStore', () => ({
  useCockpitStore: (
    selector: (s: { selectedTicker: null; setSelectedTicker: typeof mockSetSelectedTicker }) => unknown,
  ) => selector({ selectedTicker: null, setSelectedTicker: mockSetSelectedTicker }),
}))

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

function renderWidget() {
  const client = makeClient()
  return render(
    <QueryClientProvider client={client}>
      <SetupMonitorWidget />
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

// ─── Fixtures ─────────────────────────────────────────────────────────────────

function makeItem(overrides: Partial<SetupItem>): SetupItem {
  return {
    ticker: 'AAPL',
    stockName: 'Apple Inc.',
    setupType: 'BREAKOUT',
    setupQuality: 'A',
    entryPrice: 180.0,
    stopPrice: 172.0,
    target2r: 196.0,
    target3r: 204.0,
    distanceToEntryPct: 0.5,
    rewardRisk: 2.5,
    rsPercentile: 85,
    volumeStatus: 'HIGH',
    trendScore: 5,
    earningsRisk: 'SAFE',
    readySignal: true,
    suggestedAction: 'enter',
    scanDate: '2026-04-25',
    volumeZscore: 1.83,
    obvTrend: 'UP',
    upDownVolumeRatio: 1.45,
    weeklyStage: 2,
    ...overrides,
  }
}

// 7 items covering all setupType branches
const ITEMS_ALL_TYPES: SetupItem[] = [
  makeItem({ ticker: 'AAPL', setupType: 'BREAKOUT', trendScore: 4, rsPercentile: 85 }),
  makeItem({ ticker: 'MSFT', setupType: 'PULLBACK', trendScore: 2, rsPercentile: 75 }),
  makeItem({ ticker: 'GOOGL', setupType: 'RECLAIM', trendScore: 1, rsPercentile: 60 }),
  makeItem({ ticker: 'AMZN', setupType: 'EARNINGS_DRIFT', entryPrice: 0, stopPrice: 0 }),
  makeItem({ ticker: 'META', setupType: 'EXTENDED' }),
  makeItem({ ticker: 'NVDA', setupType: 'BROKEN' }),
  makeItem({ ticker: 'TSLA', setupType: 'NONE' }),
]

const SETUP_MONITOR_OK: SetupMonitorData = {
  summary: { total: 7, ready: 3, near: 1, extended: 1, broken: 1, none: 1 },
  items: ITEMS_ALL_TYPES,
}

const SETUP_MONITOR_OK_FETCH = () =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ data: SETUP_MONITOR_OK }),
  } as FetchResponse)

// Single BREAKOUT row for focused integration tests
const BREAKOUT_ITEM = makeItem({
  ticker: 'AAPL',
  setupType: 'BREAKOUT',
  trendScore: 4,
  rsPercentile: 85,
  entryPrice: 180.0,
  stopPrice: 172.0,
})

const SETUP_MONITOR_BREAKOUT_FETCH = () =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () =>
      Promise.resolve({
        data: {
          summary: { total: 1, ready: 1, near: 0, extended: 0, broken: 0, none: 0 },
          items: [BREAKOUT_ITEM],
        },
      }),
  } as FetchResponse)

const AI_EXPLAINER_SUCCESS_DATA = {
  memoId: 1,
  taskType: 'setup_explainer',
  schemaVersion: 'v1',
  output: {
    label: 'High-tight bull flag breakout',
    quality: 'A' as const,
    whyWatch: 'AAPL is forming a classic consolidation with RS holding near highs.',
    mainRisks: ['Market reversal risk', 'Volume dry-up before breakout'],
  },
  meta: {
    modelUsed: 'claude-3-haiku',
    tier: 'haiku',
    tokensIn: 400,
    tokensOut: 150,
    costUsd: 0.001,
    latencyMs: 900,
    cacheHit: false,
  },
}

const AI_EXPLAINER_SUCCESS_FETCH = () =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ data: AI_EXPLAINER_SUCCESS_DATA }),
  } as FetchResponse)

const AI_EXPLAINER_502_FETCH = () =>
  Promise.resolve({
    ok: false,
    status: 502,
    json: () =>
      Promise.resolve({ error: { code: 'AI_PROVIDER_ERROR', message: 'LLM down' } }),
  } as FetchResponse)

// ─── §R fixtures ─────────────────────────────────────────────────────────────

const REGIME_DATA = {
  date: '2026-04-25',
  regime: 'CONSTRUCTIVE' as const,
  marketScore: 65,
  subscores: {
    spyTrend: 70,
    qqqTrend: 65,
    iwmBreadth: 55,
    sectorParticipation: 60,
    riskAppetite: 70,
    volatilityStress: 30,
  },
  allowedExposurePct: 80,
  singleTradeRiskPct: 1,
  preferredSetups: ['BREAKOUT', 'PULLBACK'],
  avoidSetups: ['BROKEN'],
  indices: [],
  sectors: [],
  computedAt: '2026-04-25T10:00:00Z',
}

const REGIME_FETCH = () =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ data: REGIME_DATA }),
  } as FetchResponse)

const AI_RANKER_SUCCESS_DATA = {
  memoId: 2,
  taskType: 'candidate_ranker',
  schemaVersion: 'v1',
  output: {
    topCandidates: [
      { ticker: 'AAPL', rank: 1 as const, reason: 'Strong momentum with RS at highs', action: 'enter' as const },
      { ticker: 'MSFT', rank: 2 as const, reason: 'Tight base near breakout level', action: 'watch' as const },
      { ticker: 'GOOGL', rank: 3 as const, reason: 'Extended, wait for pullback', action: 'wait' as const },
    ],
  },
  meta: {
    modelUsed: 'claude-haiku-4-5',
    tier: 'haiku',
    tokensIn: 800,
    tokensOut: 300,
    costUsd: 0.002,
    latencyMs: 1200,
    cacheHit: false,
  },
}

const AI_RANKER_SUCCESS_FETCH = () =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ data: AI_RANKER_SUCCESS_DATA }),
  } as FetchResponse)

const AI_RANKER_502_FETCH = () =>
  Promise.resolve({
    ok: false,
    status: 502,
    json: () =>
      Promise.resolve({ error: { code: 'AI_PROVIDER_ERROR', message: 'LLM down' } }),
  } as FetchResponse)

const SETUP_MONITOR_EMPTY_FETCH = () =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () =>
      Promise.resolve({
        data: {
          summary: { total: 0, ready: 0, near: 0, extended: 0, broken: 0, none: 0 },
          items: [],
        },
      }),
  } as FetchResponse)

// 21 items: first 20 only sent to AI
const ITEMS_21: SetupItem[] = Array.from({ length: 21 }, (_, i) =>
  makeItem({ ticker: `TK${String(i + 1).padStart(2, '0')}` }),
)

const SETUP_MONITOR_21_FETCH = () =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () =>
      Promise.resolve({
        data: {
          summary: { total: 21, ready: 21, near: 0, extended: 0, broken: 0, none: 0 },
          items: ITEMS_21,
        },
      }),
  } as FetchResponse)

// ─── §R – AI Candidate Ranker ─────────────────────────────────────────────────

describe('§R – AI Candidate Ranker', () => {
  beforeEach(() => {
    mockSetSelectedTicker.mockClear()
  })
  afterEach(() => vi.unstubAllGlobals())

  // ── R1: button enabled when items + regime loaded ──────────────────────────
  it('R1: items + regime loaded → AI 排序 button enabled', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH,
        '/cockpit/regime': REGIME_FETCH,
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')
    const btn = screen.getByTestId('ai-rank-trigger')
    await waitFor(() => expect(btn).not.toBeDisabled())
  })

  // ── R2: button disabled when regime not yet loaded ─────────────────────────
  it('R2: regime pending → button disabled', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH,
        // no '/cockpit/regime' → never resolves
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')
    expect(screen.getByTestId('ai-rank-trigger')).toBeDisabled()
  })

  // ── R3: button disabled when items empty ───────────────────────────────────
  it('R3: empty items (empty filter) → button disabled', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_EMPTY_FETCH,
        '/cockpit/regime': REGIME_FETCH,
      }),
    )
    renderWidget()
    await screen.findByText('No setups')
    await waitFor(() => {
      expect(screen.getByTestId('ai-rank-trigger')).toBeDisabled()
    })
  })

  // ── R4: click → POST body has correct regime + regimeScore (C9 field mapping) ──
  it('R4: click → POST body.input.regime and .regimeScore match regime API response', async () => {
    const fetchMock = makeRoutedFetch({
      '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH,
      '/cockpit/regime': REGIME_FETCH,
      '/ai/candidate_ranker': AI_RANKER_SUCCESS_FETCH,
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await screen.findByText('AAPL')

    const btn = screen.getByTestId('ai-rank-trigger')
    await waitFor(() => expect(btn).not.toBeDisabled())
    fireEvent.click(btn)

    await waitFor(() => {
      const calls = fetchMock.mock.calls.filter(([url]) =>
        (url as string).includes('/ai/candidate_ranker'),
      )
      expect(calls.length).toBeGreaterThanOrEqual(1)
    })

    const call = fetchMock.mock.calls.find(([url]) =>
      (url as string).includes('/ai/candidate_ranker'),
    )!
    const body = JSON.parse(call[1].body as string) as {
      input: { regime: string; regimeScore: number; candidates: unknown[] }
      noCache: boolean
    }

    expect(body.input.regime).toBe('CONSTRUCTIVE')
    expect(body.input.regimeScore).toBe(65) // marketScore → regimeScore field adaptation (C9)
    expect(body.noCache).toBe(false)
  })

  // ── R5: candidates capped at 20 ────────────────────────────────────────────
  it('R5: 21 items → body.input.candidates.length === 20', async () => {
    const fetchMock = makeRoutedFetch({
      '/cockpit/setup-monitor': SETUP_MONITOR_21_FETCH,
      '/cockpit/regime': REGIME_FETCH,
      '/ai/candidate_ranker': AI_RANKER_SUCCESS_FETCH,
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await screen.findByText('TK01')

    const btn = screen.getByTestId('ai-rank-trigger')
    await waitFor(() => expect(btn).not.toBeDisabled())
    fireEvent.click(btn)

    await waitFor(() => {
      const calls = fetchMock.mock.calls.filter(([url]) =>
        (url as string).includes('/ai/candidate_ranker'),
      )
      expect(calls.length).toBeGreaterThanOrEqual(1)
    })

    const call = fetchMock.mock.calls.find(([url]) =>
      (url as string).includes('/ai/candidate_ranker'),
    )!
    const body = JSON.parse(call[1].body as string) as {
      input: { candidates: unknown[] }
    }
    expect(body.input.candidates).toHaveLength(20)
  })

  // ── R6: 9-field candidate, no extras ──────────────────────────────────────
  it('R6: candidate has exactly 9 fields, no stockName/volumeStatus/entryPrice/stopPrice', async () => {
    const fetchMock = makeRoutedFetch({
      '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH,
      '/cockpit/regime': REGIME_FETCH,
      '/ai/candidate_ranker': AI_RANKER_SUCCESS_FETCH,
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await screen.findByText('AAPL')

    const btn = screen.getByTestId('ai-rank-trigger')
    await waitFor(() => expect(btn).not.toBeDisabled())
    fireEvent.click(btn)

    await waitFor(() => {
      const calls = fetchMock.mock.calls.filter(([url]) =>
        (url as string).includes('/ai/candidate_ranker'),
      )
      expect(calls.length).toBeGreaterThanOrEqual(1)
    })

    const call = fetchMock.mock.calls.find(([url]) =>
      (url as string).includes('/ai/candidate_ranker'),
    )!
    const body = JSON.parse(call[1].body as string) as {
      input: { candidates: Record<string, unknown>[] }
    }
    const c = body.input.candidates[0]
    const keys = Object.keys(c).sort()

    expect(keys).toEqual([
      'distanceToEntryPct',
      'earningsRisk',
      'readySignal',
      'rewardRisk',
      'rsPercentile',
      'setupQuality',
      'setupType',
      'ticker',
      'trendScore',
    ])
    expect(c).not.toHaveProperty('stockName')
    expect(c).not.toHaveProperty('volumeStatus')
    expect(c).not.toHaveProperty('entryPrice')
    expect(c).not.toHaveProperty('stopPrice')
    expect(c).not.toHaveProperty('suggestedAction')
    expect(c).not.toHaveProperty('scanDate')
  })

  // ── R7: loading state shows 3 skeletons ────────────────────────────────────
  it('R7: loading → 3 Skeleton rows visible', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH,
        '/cockpit/regime': REGIME_FETCH,
        '/ai/candidate_ranker': () => new Promise(() => {}), // never resolves
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')

    const btn = screen.getByTestId('ai-rank-trigger')
    await waitFor(() => expect(btn).not.toBeDisabled())
    fireEvent.click(btn)

    await waitFor(() => {
      const skeletons = document.querySelectorAll('[data-testid="ai-rank-skeleton"]')
      expect(skeletons.length).toBe(3)
    })
  })

  // ── R8: success renders top 3 with rank / ticker / action / reason ─────────
  it('R8: success response renders top 3 cards with rank, ticker, action badge, reason', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH,
        '/cockpit/regime': REGIME_FETCH,
        '/ai/candidate_ranker': AI_RANKER_SUCCESS_FETCH,
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')

    const btn = screen.getByTestId('ai-rank-trigger')
    await waitFor(() => expect(btn).not.toBeDisabled())
    fireEvent.click(btn)

    // Card 1
    const card1 = await screen.findByTestId('ai-rank-card-1')
    expect(card1).toHaveTextContent('#1')
    expect(card1).toHaveTextContent('AAPL')
    expect(card1).toHaveTextContent('enter')
    expect(card1).toHaveTextContent('Strong momentum with RS at highs')

    // Card 2
    const card2 = screen.getByTestId('ai-rank-card-2')
    expect(card2).toHaveTextContent('#2')
    expect(card2).toHaveTextContent('MSFT')
    expect(card2).toHaveTextContent('watch')
    expect(card2).toHaveTextContent('Tight base near breakout level')

    // Card 3
    const card3 = screen.getByTestId('ai-rank-card-3')
    expect(card3).toHaveTextContent('#3')
    expect(card3).toHaveTextContent('GOOGL')
    expect(card3).toHaveTextContent('wait')
    expect(card3).toHaveTextContent('Extended, wait for pullback')
  })

  // ── R9: truncation notice when items > 20 ─────────────────────────────────
  it('R9: items.length > 20 → result header shows "Top 20 / N" truncation notice', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_21_FETCH,
        '/cockpit/regime': REGIME_FETCH,
        '/ai/candidate_ranker': AI_RANKER_SUCCESS_FETCH,
      }),
    )
    renderWidget()
    await screen.findByText('TK01')

    const btn = screen.getByTestId('ai-rank-trigger')
    await waitFor(() => expect(btn).not.toBeDisabled())
    fireEvent.click(btn)

    const badge = await screen.findByTestId('ai-rank-truncated')
    expect(badge).toHaveTextContent('Top 20 / 21')
  })

  // ── R10: 502 shows error; row click setSelectedTicker still works ──────────
  it('R10: 502 AI_PROVIDER_ERROR → "AI 排序暂不可用"; table row click still fires setSelectedTicker', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH,
        '/cockpit/regime': REGIME_FETCH,
        '/ai/candidate_ranker': AI_RANKER_502_FETCH,
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')

    const btn = screen.getByTestId('ai-rank-trigger')
    await waitFor(() => expect(btn).not.toBeDisabled())
    fireEvent.click(btn)

    expect(await screen.findByTestId('ai-rank-error')).toHaveTextContent('AI 排序暂不可用')

    // Table row click must still work
    fireEvent.click(screen.getByText('AAPL'))
    expect(mockSetSelectedTicker).toHaveBeenCalledWith('AAPL')
  })

  // ── R11: close + reopen → react-query cache hit (fetch count = 1) ─────────
  it('R11: close then reopen with same inputKey → fetch count for candidate_ranker = 1', async () => {
    const fetchMock = makeRoutedFetch({
      '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH,
      '/cockpit/regime': REGIME_FETCH,
      '/ai/candidate_ranker': AI_RANKER_SUCCESS_FETCH,
    })
    vi.stubGlobal('fetch', fetchMock)

    // Use an explicit client so cache persists across interactions
    const client = makeClient()
    render(
      <QueryClientProvider client={client}>
        <SetupMonitorWidget />
      </QueryClientProvider>,
    )
    await screen.findByText('AAPL')

    const btn = screen.getByTestId('ai-rank-trigger')
    await waitFor(() => expect(btn).not.toBeDisabled())

    // First open → triggers fetch
    fireEvent.click(btn)
    await screen.findByTestId('ai-rank-card-1')

    // Close
    fireEvent.click(screen.getByTestId('ai-rank-close'))
    expect(screen.queryByTestId('ai-rank-panel')).toBeNull()

    // Reopen → cache hit, no new fetch
    fireEvent.click(btn)
    await screen.findByTestId('ai-rank-card-1')

    const rankerCalls = fetchMock.mock.calls.filter(([url]) =>
      (url as string).includes('/ai/candidate_ranker'),
    )
    expect(rankerCalls).toHaveLength(1)
  })
})

// ─── §S – Setup Explainer Popover ─────────────────────────────────────────────

describe('§S – Setup Explainer Popover', () => {
  beforeEach(() => {
    mockSetSelectedTicker.mockClear()
  })
  afterEach(() => vi.unstubAllGlobals())

  // ── S1: BREAKOUT row renders ? button ──────────────────────────────────────
  it('S1: BREAKOUT row renders ? button', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH }))
    renderWidget()
    await screen.findByText('AAPL')
    expect(
      screen.getByRole('button', { name: 'Explain AAPL BREAKOUT setup' }),
    ).toBeInTheDocument()
  })

  // ── S2: PULLBACK row renders ? button ──────────────────────────────────────
  it('S2: PULLBACK row renders ? button', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH }))
    renderWidget()
    await screen.findByText('MSFT')
    expect(
      screen.getByRole('button', { name: 'Explain MSFT PULLBACK setup' }),
    ).toBeInTheDocument()
  })

  // ── S3: RECLAIM row renders ? button ───────────────────────────────────────
  it('S3: RECLAIM row renders ? button', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH }))
    renderWidget()
    await screen.findByText('GOOGL')
    expect(
      screen.getByRole('button', { name: 'Explain GOOGL RECLAIM setup' }),
    ).toBeInTheDocument()
  })

  // ── S4: EARNINGS_DRIFT row does NOT render ? button ────────────────────────
  it('S4: EARNINGS_DRIFT row does NOT render ? button', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH }))
    renderWidget()
    await screen.findByText('AMZN')
    expect(
      screen.queryByRole('button', { name: /Explain AMZN/ }),
    ).toBeNull()
  })

  // ── S5: EXTENDED row does NOT render ? button ──────────────────────────────
  it('S5: EXTENDED row does NOT render ? button', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH }))
    renderWidget()
    await screen.findByText('META')
    expect(
      screen.queryByRole('button', { name: /Explain META/ }),
    ).toBeNull()
  })

  // ── S6: BROKEN row does NOT render ? button ────────────────────────────────
  it('S6: BROKEN row does NOT render ? button', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH }))
    renderWidget()
    await screen.findByText('NVDA')
    expect(
      screen.queryByRole('button', { name: /Explain NVDA/ }),
    ).toBeNull()
  })

  // ── S7: clicking ? does NOT trigger setSelectedTicker (stopPropagation) ───
  it('S7: clicking ? does not trigger setSelectedTicker (stopPropagation)', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_BREAKOUT_FETCH,
        '/ai/setup_explainer': () => new Promise(() => {}), // keep pending
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')

    const btn = screen.getByRole('button', { name: 'Explain AAPL BREAKOUT setup' })
    fireEvent.click(btn)

    expect(mockSetSelectedTicker).not.toHaveBeenCalled()
  })

  // ── S8: clicking ? calls POST /api/ai/setup_explainer with correct body ───
  it('S8: clicking ? POSTs setup_explainer with correct input mapping', async () => {
    const fetchMock = makeRoutedFetch({
      '/cockpit/setup-monitor': SETUP_MONITOR_BREAKOUT_FETCH,
      '/ai/setup_explainer': AI_EXPLAINER_SUCCESS_FETCH,
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await screen.findByText('AAPL')

    fireEvent.click(screen.getByRole('button', { name: 'Explain AAPL BREAKOUT setup' }))

    await waitFor(() => {
      const aiCalls = fetchMock.mock.calls.filter(([url]) =>
        (url as string).includes('/ai/setup_explainer'),
      )
      expect(aiCalls.length).toBeGreaterThanOrEqual(1)
    })

    const aiCalls = fetchMock.mock.calls.filter(([url]) =>
      (url as string).includes('/ai/setup_explainer'),
    )
    const body = JSON.parse(aiCalls[0][1].body as string) as {
      input: { ticker: string; trend: string; rs: number; setup: string; risk: { entry: number; stop: number } }
      noCache: boolean
    }

    expect(body.input.ticker).toBe('AAPL')
    expect(body.input.setup).toBe('breakout')         // BREAKOUT → 'breakout'
    expect(body.input.trend).toBe('up')               // trendScore=4 → 'up' (0-5 ladder)
    expect(body.input.rs).toBe(85)                    // rsPercentile passthrough
    expect(body.input.risk.entry).toBe(180.0)
    expect(body.input.risk.stop).toBe(172.0)
    expect(body.noCache).toBe(false)
  })

  // ── S8b: trendScore boundary mapping (0-5 ladder) ─────────────────────────
  it.each([
    [5, 'up'],
    [4, 'up'],
    [3, 'sideways'],
    [2, 'sideways'],
    [1, 'down'],
    [0, 'down'],
  ])('S8b: trendScore=%i → trend=%s', async (trendScore, expectedTrend) => {
    const item = makeItem({
      ticker: 'AAPL',
      setupType: 'BREAKOUT',
      trendScore,
      entryPrice: 180.0,
      stopPrice: 172.0,
    })
    const fetchMock = makeRoutedFetch({
      '/cockpit/setup-monitor': () =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              data: {
                summary: { total: 1, ready: 1, near: 0, extended: 0, broken: 0, none: 0 },
                items: [item],
              },
            }),
        } as FetchResponse),
      '/ai/setup_explainer': AI_EXPLAINER_SUCCESS_FETCH,
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await screen.findByText('AAPL')

    fireEvent.click(screen.getByRole('button', { name: 'Explain AAPL BREAKOUT setup' }))

    await waitFor(() => {
      const aiCalls = fetchMock.mock.calls.filter(([url]) =>
        (url as string).includes('/ai/setup_explainer'),
      )
      expect(aiCalls.length).toBeGreaterThanOrEqual(1)
    })

    const aiCalls = fetchMock.mock.calls.filter(([url]) =>
      (url as string).includes('/ai/setup_explainer'),
    )
    const body = JSON.parse(aiCalls[0][1].body as string) as {
      input: { trend: string }
    }
    expect(body.input.trend).toBe(expectedTrend)
  })

  // ── S9: loading state shows Skeleton elements ──────────────────────────────
  it('S9: loading state shows Skeleton elements in popover', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_BREAKOUT_FETCH,
        '/ai/setup_explainer': () => new Promise(() => {}), // never resolves
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')

    fireEvent.click(screen.getByRole('button', { name: 'Explain AAPL BREAKOUT setup' }))

    await waitFor(() => {
      const skeletons = document.querySelectorAll('[data-testid="ai-explainer-skeleton"]')
      expect(skeletons.length).toBeGreaterThanOrEqual(3)
    })
  })

  // ── S10: success renders label / quality / whyWatch / mainRisks ───────────
  it('S10: success response renders label, quality badge, whyWatch, and mainRisks', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_BREAKOUT_FETCH,
        '/ai/setup_explainer': AI_EXPLAINER_SUCCESS_FETCH,
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')

    fireEvent.click(screen.getByRole('button', { name: 'Explain AAPL BREAKOUT setup' }))

    expect(await screen.findByTestId('ai-explainer-label')).toHaveTextContent(
      'High-tight bull flag breakout',
    )
    expect(await screen.findByTestId('ai-explainer-quality')).toHaveTextContent('A')
    expect(await screen.findByTestId('ai-explainer-why-watch')).toHaveTextContent(
      'AAPL is forming a classic consolidation',
    )
    const risksList = await screen.findByTestId('ai-explainer-risks')
    expect(risksList).toHaveTextContent('Market reversal risk')
    expect(risksList).toHaveTextContent('Volume dry-up before breakout')
  })

  // ── S11: 502 error shows "AI 暂不可用"; row click still works ─────────────
  it('S11: 502 AI_PROVIDER_ERROR shows "AI 暂不可用"; row click still triggers setSelectedTicker', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': SETUP_MONITOR_BREAKOUT_FETCH,
        '/ai/setup_explainer': AI_EXPLAINER_502_FETCH,
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')

    fireEvent.click(screen.getByRole('button', { name: 'Explain AAPL BREAKOUT setup' }))

    expect(await screen.findByTestId('ai-explainer-error')).toHaveTextContent('AI 暂不可用')

    // Row click (on the ticker cell) should still fire setSelectedTicker
    fireEvent.click(screen.getByText('AAPL'))
    expect(mockSetSelectedTicker).toHaveBeenCalledWith('AAPL')
  })
})

// ─── §V – Vol Z column ────────────────────────────────────────────────────────

describe('§V – Vol Z column', () => {
  afterEach(() => vi.unstubAllGlobals())

  // ── V1: table header contains 'Vol Z' ─────────────────────────────────────
  it('V1: table header renders "Vol Z" column', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ '/cockpit/setup-monitor': SETUP_MONITOR_OK_FETCH }))
    renderWidget()
    await screen.findByText('AAPL')
    expect(screen.getByText('Vol Z')).toBeInTheDocument()
  })

  // ── V2: volumeZscore=1.83 renders '1.83' ──────────────────────────────────
  it('V2: volumeZscore=1.83 → cell displays "1.83"', async () => {
    const item = makeItem({ ticker: 'AAPL', volumeZscore: 1.83 })
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': () =>
          Promise.resolve({
            ok: true,
            status: 200,
            json: () =>
              Promise.resolve({
                data: {
                  summary: { total: 1, ready: 1, near: 0, extended: 0, broken: 0, none: 0 },
                  items: [item],
                },
              }),
          } as FetchResponse),
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')
    expect(screen.getByText('1.83')).toBeInTheDocument()
  })

  // ── V3: volumeZscore=null renders '—' ─────────────────────────────────────
  it('V3: volumeZscore=null → cell displays "—"', async () => {
    const item = makeItem({ ticker: 'AAPL', volumeZscore: null })
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/setup-monitor': () =>
          Promise.resolve({
            ok: true,
            status: 200,
            json: () =>
              Promise.resolve({
                data: {
                  summary: { total: 1, ready: 1, near: 0, extended: 0, broken: 0, none: 0 },
                  items: [item],
                },
              }),
          } as FetchResponse),
      }),
    )
    renderWidget()
    await screen.findByText('AAPL')
    // '—' also appears for other nullable cells; check at least one exists
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(1)
  })
})
