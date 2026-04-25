import { render, screen, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest'
import { createChart } from 'lightweight-charts'
import { CockpitChartWidget } from '../CockpitChartWidget'
import { useCockpitStore } from '@/store/cockpitStore'

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('lightweight-charts', () => {
  const mockSeries = {
    setData: vi.fn(),
    priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    createPriceLine: vi.fn(() => ({})),
    removePriceLine: vi.fn(),
  }
  const mockChart = {
    addSeries: vi.fn(() => mockSeries),
    applyOptions: vi.fn(),
    remove: vi.fn(),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
  }
  return {
    createChart: vi.fn(() => mockChart),
    CandlestickSeries: 'CandlestickSeries',
    HistogramSeries: 'HistogramSeries',
    LineSeries: 'LineSeries',
    LineStyle: { Solid: 0, Dotted: 1, Dashed: 2, LargeDashed: 3, SparseDotted: 4 },
  }
})

// ── ResizeObserver mock ────────────────────────────────────────────────────

let capturedResizeCallback: ResizeObserverCallback | null = null

class MockResizeObserver {
  constructor(cb: ResizeObserverCallback) {
    capturedResizeCallback = cb
  }
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()
}

beforeAll(() => {
  vi.stubGlobal('ResizeObserver', MockResizeObserver)
})
afterAll(() => {
  vi.unstubAllGlobals()
})

// ── Mock data ──────────────────────────────────────────────────────────────

const mockChartData = {
  ticker: 'NVDA',
  bars: [{ date: '2026-04-24', open: 845, high: 852, low: 840, close: 850, volume: 31250000 }],
  mas: {
    '10': [{ date: '2026-04-24', value: 842 }],
    '21': [{ date: '2026-04-24', value: 835 }],
    '50': [{ date: '2026-04-24', value: 820 }],
    '150': [{ date: '2026-04-24', value: 780 }],
    '200': [{ date: '2026-04-24', value: 760 }],
  },
  atr: [{ date: '2026-04-24', value: 15 }],
  avwap: { anchor: '2026-02-15', series: [{ date: '2026-02-15', value: 770 }] },
}

const mockDecisionData = {
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
}

// ── Helpers ────────────────────────────────────────────────────────────────

function makeFetch(
  chartOverride?: Partial<typeof mockChartData> | null,
  decisionStatus?: number,
) {
  return vi.fn((url: string) => {
    if (url.includes('/cockpit/chart/')) {
      const data = chartOverride === null ? null : { ...mockChartData, ...chartOverride }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data }),
      })
    }
    if (url.includes('/cockpit/decision/')) {
      if (decisionStatus === 404) {
        return Promise.resolve({
          ok: false,
          status: 404,
          json: () =>
            Promise.resolve({ error: { code: 'NOT_FOUND', message: 'not found' } }),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: mockDecisionData }),
      })
    }
    return Promise.reject(new Error(`Unexpected URL: ${url}`))
  }) as unknown as typeof fetch
}

function renderWidget() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <CockpitChartWidget />
    </QueryClientProvider>,
  )
}

function getMockChart() {
  return vi.mocked(createChart).mock.results[0]?.value as {
    addSeries: ReturnType<typeof vi.fn>
    applyOptions: ReturnType<typeof vi.fn>
    remove: ReturnType<typeof vi.fn>
    timeScale: ReturnType<typeof vi.fn>
  }
}

// ── Tests ──────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  capturedResizeCallback = null
  useCockpitStore.setState({ selectedTicker: null })
})

afterEach(() => {
  useCockpitStore.setState({ selectedTicker: null })
})

describe('S3 – empty state when no ticker', () => {
  it('shows prompt text and makes no fetch', () => {
    vi.stubGlobal('fetch', vi.fn())
    renderWidget()
    expect(screen.getByText('请从 Setup Monitor 选择一只股票')).toBeInTheDocument()
    expect(global.fetch).not.toHaveBeenCalled()
  })
})

describe('S4 – loading and chart creation', () => {
  it('shows loading state then creates chart with all series', async () => {
    vi.stubGlobal('fetch', makeFetch())
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    expect(screen.getByText('Loading chart…')).toBeInTheDocument()

    await waitFor(() => {
      expect(vi.mocked(createChart)).toHaveBeenCalledTimes(1)
    })

    const chart = getMockChart()
    // candle(1) + volume(1) + MA*5(5) + AVWAP(1) = 8
    expect(chart.addSeries).toHaveBeenCalledTimes(8)
  })
})

describe('S5 – decision price lines', () => {
  it('createPriceLine called 4 times with price in title', async () => {
    vi.stubGlobal('fetch', makeFetch())
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(vi.mocked(createChart)).toHaveBeenCalledTimes(1)
    })

    const chart = getMockChart()
    const series = chart.addSeries.mock.results[0].value as {
      createPriceLine: ReturnType<typeof vi.fn>
    }

    await waitFor(() => {
      expect(series.createPriceLine).toHaveBeenCalledTimes(4)
    })

    const calls = series.createPriceLine.mock.calls as Array<[{ title: string; price: number }]>
    expect(calls[0][0].title).toContain('850')
    expect(calls[1][0].title).toContain('820')
    expect(calls[2][0].title).toContain('910')
    expect(calls[3][0].title).toContain('940')
  })
})

describe('S6 – decision 404 → chart renders, no price lines', () => {
  it('chart is created, createPriceLine never called', async () => {
    vi.stubGlobal('fetch', makeFetch(undefined, 404))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(vi.mocked(createChart)).toHaveBeenCalledTimes(1)
    })

    const chart = getMockChart()
    const series = chart.addSeries.mock.results[0].value as {
      createPriceLine: ReturnType<typeof vi.fn>
    }

    // Give time for decision query to settle
    await new Promise((r) => setTimeout(r, 50))
    expect(series.createPriceLine).not.toHaveBeenCalled()
  })
})

describe('S7 – ticker switch: old chart removed, new chart created', () => {
  it('chart.remove() called and createChart called twice', async () => {
    vi.stubGlobal('fetch', makeFetch())
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(vi.mocked(createChart)).toHaveBeenCalledTimes(1)
    })

    const oldChart = getMockChart()

    act(() => {
      useCockpitStore.setState({ selectedTicker: 'CRWD' })
    })

    await waitFor(() => {
      expect(vi.mocked(createChart)).toHaveBeenCalledTimes(2)
    })

    expect(oldChart.remove).toHaveBeenCalled()
  })
})

describe('S8 – ResizeObserver → chart.applyOptions called', () => {
  it('resize triggers chart applyOptions with new dimensions', async () => {
    vi.stubGlobal('fetch', makeFetch())
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(vi.mocked(createChart)).toHaveBeenCalledTimes(1)
    })

    expect(capturedResizeCallback).not.toBeNull()

    const chart = getMockChart()
    act(() => {
      capturedResizeCallback!(
        [{ contentRect: { width: 800, height: 600 } } as ResizeObserverEntry],
        {} as ResizeObserver,
      )
    })

    expect(chart.applyOptions).toHaveBeenCalledWith({ width: 800, height: 600 })
  })
})
