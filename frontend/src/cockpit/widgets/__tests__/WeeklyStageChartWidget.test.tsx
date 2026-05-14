import { render, screen, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest'
import { createChart } from 'lightweight-charts'
import { WeeklyStageChartWidget } from '../WeeklyStageChartWidget'
import { useCockpitStore } from '@/store/cockpitStore'

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('lightweight-charts', () => {
  const mockSeries = {
    setData: vi.fn(),
    priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
  }
  const mockChart = {
    addSeries: vi.fn(() => mockSeries),
    applyOptions: vi.fn(),
    remove: vi.fn(),
    timeScale: vi.fn(() => ({ fitContent: vi.fn(), setVisibleRange: vi.fn() })),
  }
  return {
    createChart: vi.fn(() => mockChart),
    CandlestickSeries: 'CandlestickSeries',
    HistogramSeries: 'HistogramSeries',
    LineSeries: 'LineSeries',
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

const oneBar = { date: '2026-04-18', open: 200, high: 210, low: 195, close: 205, volume: 5000000 }

function makeWeeklyData(stageNum: number, barsOverride?: typeof oneBar[]) {
  const bars = barsOverride ?? [oneBar]
  return {
    ticker: 'NVDA',
    weeklyBars: bars,
    weeklyMas: {
      '10': bars.length >= 1 ? [{ date: oneBar.date, value: 198 }] : [],
      '30': bars.length >= 1 ? [{ date: oneBar.date, value: 190 }] : [],
      '40': bars.length >= 1 ? [{ date: oneBar.date, value: 185 }] : [],
    },
    stage: {
      stage: stageNum,
      weeklyClose: bars.length > 0 ? bars[bars.length - 1].close : null,
      weeklyMa10: bars.length > 0 ? 198 : null,
      weeklyMa30: bars.length > 0 ? 190 : null,
      weeklyMa40: bars.length > 0 ? 185 : null,
      slope30W: stageNum === 2 ? 0.8 : stageNum === 4 ? -0.9 : null,
      scanDate: bars.length > 0 ? oneBar.date : null,
    },
  }
}

function makeEmptyWeeklyData(stageNum = 0) {
  return {
    ticker: 'NVDA',
    weeklyBars: [],
    weeklyMas: { '10': [], '30': [], '40': [] },
    stage: {
      stage: stageNum,
      weeklyClose: null,
      weeklyMa10: null,
      weeklyMa30: null,
      weeklyMa40: null,
      slope30W: null,
      scanDate: null,
    },
  }
}

function makeFetch(data: object) {
  return vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data }),
    }),
  ) as unknown as typeof fetch
}

// ── Helpers ────────────────────────────────────────────────────────────────

function renderWidget() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <WeeklyStageChartWidget />
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

// ── Setup / teardown ───────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  capturedResizeCallback = null
  useCockpitStore.setState({ selectedTicker: null })
})
afterEach(() => {
  useCockpitStore.setState({ selectedTicker: null })
})

// ── Tests (Standards 6-12) ─────────────────────────────────────────────────

describe('Standard 6 – no ticker → empty state, no fetch', () => {
  it('shows prompt and makes no fetch call', () => {
    vi.stubGlobal('fetch', vi.fn())
    renderWidget()
    expect(screen.getByText('请从 Setup Monitor 选择一只股票')).toBeInTheDocument()
    expect(global.fetch).not.toHaveBeenCalled()
  })
})

describe('Standard 7 – ticker + normal data → chart created, addSeries x5', () => {
  it('createChart called once, addSeries called 5 times (candle+volume+MA×3)', async () => {
    vi.stubGlobal('fetch', makeFetch(makeWeeklyData(2)))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    expect(screen.getByText('Loading chart…')).toBeInTheDocument()

    await waitFor(() => {
      expect(vi.mocked(createChart)).toHaveBeenCalledTimes(1)
    })

    const chart = getMockChart()
    expect(chart.addSeries).toHaveBeenCalledTimes(5)
  })
})

describe('Standard 8 – weeklyBars=[] + stage=0 → "数据不足", no createChart, gray header', () => {
  it('renders 数据不足, createChart not called, header shows Stage 0 Unknown', async () => {
    vi.stubGlobal('fetch', makeFetch(makeEmptyWeeklyData(0)))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByText('数据不足')).toBeInTheDocument()
    })

    expect(vi.mocked(createChart)).not.toHaveBeenCalled()

    const header = screen.getByTestId('weekly-stage-header')
    expect(header).toHaveTextContent('NVDA')
    expect(header).toHaveTextContent('Stage 0')
    expect(header).toHaveTextContent('Unknown')
    expect(header.dataset.stage).toBe('0')
  })
})

describe('Standard 9 – stage=2 → green header, "Stage 2 · Advancing"', () => {
  it('header text and data-stage correct for stage=2', async () => {
    vi.stubGlobal('fetch', makeFetch(makeWeeklyData(2)))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByTestId('weekly-stage-header')).toHaveTextContent('Stage 2 · Advancing')
    })

    const header = screen.getByTestId('weekly-stage-header')
    expect(header.dataset.stage).toBe('2')
    // readToken returns fallback #10b981 in jsdom (CSS vars not set)
    expect(header.style.background).toBeTruthy()
  })
})

describe('Standard 10 – stage=4 → red header, "Stage 4 · Declining"', () => {
  it('header text and data-stage correct for stage=4', async () => {
    vi.stubGlobal('fetch', makeFetch(makeWeeklyData(4)))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByTestId('weekly-stage-header')).toHaveTextContent('Stage 4 · Declining')
    })

    const header = screen.getByTestId('weekly-stage-header')
    expect(header.dataset.stage).toBe('4')
    expect(header.style.background).toBeTruthy()
  })
})

describe('Standard 11 – stage=1 and stage=3 → same yellow token', () => {
  it('stage=1 header shows Stage 1 · Base with data-stage=1', async () => {
    vi.stubGlobal('fetch', makeFetch(makeWeeklyData(1)))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByTestId('weekly-stage-header')).toHaveTextContent('Stage 1 · Base')
    })
    expect(screen.getByTestId('weekly-stage-header').dataset.stage).toBe('1')
  })

  it('stage=3 header shows Stage 3 · Distribution with data-stage=3', async () => {
    vi.stubGlobal('fetch', makeFetch(makeWeeklyData(3)))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByTestId('weekly-stage-header')).toHaveTextContent('Stage 3 · Distribution')
    })
    expect(screen.getByTestId('weekly-stage-header').dataset.stage).toBe('3')
  })

  it('stage=1 and stage=3 use same background fallback (#f59e0b)', async () => {
    // Stage 1
    vi.stubGlobal('fetch', makeFetch(makeWeeklyData(1)))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    const { unmount } = renderWidget()
    await waitFor(() =>
      expect(screen.getByTestId('weekly-stage-header')).toHaveTextContent('Stage 1'),
    )
    const bg1 = screen.getByTestId('weekly-stage-header').style.background
    unmount()

    // Stage 3
    vi.clearAllMocks()
    useCockpitStore.setState({ selectedTicker: null })
    vi.stubGlobal('fetch', makeFetch(makeWeeklyData(3)))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()
    await waitFor(() =>
      expect(screen.getByTestId('weekly-stage-header')).toHaveTextContent('Stage 3'),
    )
    const bg3 = screen.getByTestId('weekly-stage-header').style.background

    expect(bg1).toBe(bg3)
  })
})

describe('Standard 12 – ticker switch → old chart removed, createChart called twice', () => {
  it('chart.remove() called on ticker change, createChart total=2', async () => {
    vi.stubGlobal('fetch', makeFetch(makeWeeklyData(2)))
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
