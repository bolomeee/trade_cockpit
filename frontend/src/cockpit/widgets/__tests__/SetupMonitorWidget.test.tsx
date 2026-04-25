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
