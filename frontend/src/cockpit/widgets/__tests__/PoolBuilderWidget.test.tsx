import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PoolBuilderWidget } from '../PoolBuilderWidget'
import { PoolFilterBar } from '../_poolFilterBar'
import { COCKPIT_WIDGET_REGISTRY, getCockpitDefaultLayout } from '../../CockpitRegistry'

// ─── Mocks ────────────────────────────────────────────────────────────────────

vi.mock('@/lib/api/watchlist', () => ({
  addStock: vi.fn().mockResolvedValue({ ticker: 'NVDA', id: 1, isActive: true }),
}))

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

function renderWidget(client?: QueryClient) {
  const c = client ?? makeClient()
  return render(
    <QueryClientProvider client={c}>
      <PoolBuilderWidget />
    </QueryClientProvider>,
  )
}

type FetchResponse = { ok: boolean; status: number; json: () => Promise<unknown> }

function makeOkResponse(data: unknown): FetchResponse {
  return { ok: true, status: 200, json: () => Promise.resolve({ data, message: 'success' }) }
}

function makeErrResponse(status: number): FetchResponse {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({ error: { code: 'ERR', message: 'error' } }),
  }
}

function makeRoutedFetch(routes: Record<string, () => Promise<FetchResponse>>) {
  return vi.fn().mockImplementation((url: string) => {
    for (const [pattern, handler] of Object.entries(routes)) {
      if (url.includes(pattern)) return handler()
    }
    return new Promise(() => {})
  })
}

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const FUNNEL = { tradable: 1850, trend: 820, rs: 210, fundamental: 95, action: 22 }

const POOL_ITEM = {
  ticker: 'NVDA',
  name: 'NVIDIA Corp',
  sector: 'XLK',
  price: 850.0,
  trendScore: 5,
  rsPercentile: 88,
  setupType: 'BREAKOUT',
  distanceToPivotPct: 1.25,
  distanceTo50maPct: 3.6,
  earningsDate: '2026-05-22',
  daysUntilEarnings: 28,
  revenueGrowthYoy: 56.0,
  suggestedAction: 'enter',
  inWatchlist: false,
}

const POOL_DATA = { funnel: FUNNEL, items: [POOL_ITEM] }

// ─── Tests: widget states ─────────────────────────────────────────────────────

describe('T1 – Loading state', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows Loading… while query is pending', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))
    renderWidget()
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })
})

describe('T2 – Error state', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows error text when query fails', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/pool': () => Promise.resolve(makeErrResponse(500)),
      }),
    )
    renderWidget()
    await screen.findByText('Failed to load pool data')
  })
})

describe('T3 – Empty state', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows "No candidates" when funnel all-zero and items empty', async () => {
    const emptyData = {
      funnel: { tradable: 0, trend: 0, rs: 0, fundamental: 0, action: 0 },
      items: [],
    }
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/pool': () => Promise.resolve(makeOkResponse(emptyData)),
      }),
    )
    renderWidget()
    await screen.findByText('No candidates')
  })
})

describe('T4 – Funnel thousands separator', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('renders all 5 funnel counts with en-US thousands formatting', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/pool': () => Promise.resolve(makeOkResponse(POOL_DATA)),
      }),
    )
    renderWidget()
    await screen.findByText('1,850')
    expect(screen.getByText('820')).toBeInTheDocument()
    expect(screen.getByText('210')).toBeInTheDocument()
    expect(screen.getByText('95')).toBeInTheDocument()
    expect(screen.getByText('22')).toBeInTheDocument()
  })
})

describe('T5 – Funnel segment click toggles highlight', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('clicking a funnel step sets aria-pressed=true; clicking again resets', async () => {
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/pool': () => Promise.resolve(makeOkResponse(POOL_DATA)),
      }),
    )
    renderWidget()
    await screen.findByText('1,850')

    const tradableBtn = screen.getByRole('button', { name: /tradable/i })
    expect(tradableBtn).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(tradableBtn)
    expect(tradableBtn).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(tradableBtn)
    expect(tradableBtn).toHaveAttribute('aria-pressed', 'false')
  })
})

describe('T6 – Table renders data; null fields show —', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('renders all columns; null trendScore / distanceToPivotPct / revenueGrowthYoy show —', async () => {
    const nullItem = {
      ...POOL_ITEM,
      trendScore: null,
      distanceToPivotPct: null,
      distanceTo50maPct: null,
      daysUntilEarnings: null,
      revenueGrowthYoy: null,
      suggestedAction: null,
    }
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/pool': () =>
          Promise.resolve(makeOkResponse({ ...POOL_DATA, items: [nullItem] })),
      }),
    )
    renderWidget()
    await screen.findByText('NVDA')
    expect(screen.getByText('XLK')).toBeInTheDocument()
    expect(screen.getByText('$850.00')).toBeInTheDocument()
    // null fields
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(4)
  })
})

describe('T7 – Filter debounce 300ms', () => {
  afterEach(() => vi.useRealTimers())

  it('onChange not called before 300ms; called with new value after 300ms', () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<PoolFilterBar value={{}} onChange={onChange} />)

    const trendInput = screen.getByPlaceholderText('3')
    fireEvent.change(trendInput, { target: { value: '4' } })

    act(() => vi.advanceTimersByTime(299))
    expect(onChange).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(1))
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ trendScoreMin: 4 }))
  })
})

describe('T8 – [+ Add] click → addStock + invalidate both query keys', () => {
  beforeEach(() => vi.unstubAllGlobals())
  afterEach(() => vi.unstubAllGlobals())

  it('calls addStock and invalidates cockpit-pool + watchlist', async () => {
    const { addStock } = await import('@/lib/api/watchlist')
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/pool': () => Promise.resolve(makeOkResponse(POOL_DATA)),
        '/watchlist': () => Promise.resolve(makeOkResponse({ ticker: 'NVDA', id: 1 })),
      }),
    )

    const client = makeClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries').mockResolvedValue()
    render(
      <QueryClientProvider client={client}>
        <PoolBuilderWidget />
      </QueryClientProvider>,
    )

    await screen.findByText('NVDA')
    const addBtn = screen.getByRole('button', { name: /Add NVDA/i })
    fireEvent.click(addBtn)

    await waitFor(() => {
      expect(addStock).toHaveBeenCalledWith('NVDA')
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['cockpit-pool'] })
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['watchlist'] })
    })
  })
})

describe('T9 – inWatchlist=true row shows disabled button', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('button is disabled and shows ✓ when inWatchlist=true', async () => {
    const inWlItem = { ...POOL_ITEM, inWatchlist: true }
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        '/cockpit/pool': () =>
          Promise.resolve(makeOkResponse({ ...POOL_DATA, items: [inWlItem] })),
      }),
    )
    renderWidget()
    await screen.findByText('NVDA')

    const btn = screen.getByRole('button', { name: /NVDA in watchlist/i })
    expect(btn).toBeDisabled()
    expect(btn).toHaveTextContent('✓')
  })
})

// ─── Tests: Registry ──────────────────────────────────────────────────────────

describe('T10 – Registry', () => {
  it('cockpit.pool-builder manifest is registered with category pool', () => {
    expect(COCKPIT_WIDGET_REGISTRY['cockpit.pool-builder']).toBeDefined()
    expect(COCKPIT_WIDGET_REGISTRY['cockpit.pool-builder'].category).toBe('pool')
    expect(COCKPIT_WIDGET_REGISTRY['cockpit.pool-builder'].defaultLayout).toMatchObject({
      x: 0,
      y: 22,
      w: 12,
    })
  })

  it('getCockpitDefaultLayout includes cockpit.pool-builder', () => {
    const layout = getCockpitDefaultLayout()
    const entry = layout.find((item) => item.i === 'cockpit.pool-builder')
    expect(entry).toBeDefined()
  })
})
