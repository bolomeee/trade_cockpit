import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ChartWidget } from '../ChartWidget'
import { ApiError } from '@/lib/api/client'
import { useAppStore } from '@/store/useAppStore'
import { getStockChart } from '@/lib/api/stocks'
import { getSignals } from '@/lib/api/signals'
import { addStock } from '@/lib/api/watchlist'

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('@/store/useAppStore', () => ({ useAppStore: vi.fn() }))
vi.mock('@/lib/api/stocks', () => ({ getStockChart: vi.fn() }))
vi.mock('@/lib/api/signals', () => ({ getSignals: vi.fn() }))
vi.mock('@/lib/api/watchlist', () => ({ addStock: vi.fn() }))
vi.mock('@/components/features/stock-detail/PriceChart', () => ({
  PriceChart: () => <div data-testid="price-chart" />,
}))
vi.mock('@/components/ui/skeleton', () => ({
  Skeleton: () => <div data-testid="skeleton" />,
}))

// ── Helpers ────────────────────────────────────────────────────────────────

const SYMBOL = 'AAPL'

const mockChartData = { ticker: SYMBOL, bars: [], mas: {} }

const signalsWithout = [{ ticker: 'NVDA', name: 'NVIDIA', signal: 'BREAKOUT', price: 900 }]
const signalsWith = [
  { ticker: 'NVDA', name: 'NVIDIA', signal: 'BREAKOUT', price: 900 },
  { ticker: SYMBOL, name: 'Apple', signal: 'BREAKOUT', price: 180 },
]

function setupStore(symbol: string | null = SYMBOL) {
  vi.mocked(useAppStore).mockImplementation((selector: (s: { selectedSymbol: string | null }) => unknown) =>
    selector({ selectedSymbol: symbol }),
  )
}

function renderWidget() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return { qc, ...render(<QueryClientProvider client={qc}><ChartWidget /></QueryClientProvider>) }
}

// ── Tests ──────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getStockChart).mockResolvedValue(mockChartData as never)
  vi.mocked(getSignals).mockResolvedValue(signalsWithout as never)
  vi.mocked(addStock).mockResolvedValue(undefined as never)
})

describe('T1 – button enabled when symbol not in watchlist', () => {
  it('renders enabled CirclePlus button', async () => {
    setupStore(SYMBOL)
    renderWidget()

    await screen.findByTestId('price-chart')
    const btn = screen.getByTitle('添加到 watchlist')
    expect(btn).not.toBeDisabled()
  })
})

describe('T2 – button disabled when symbol already in watchlist', () => {
  it('button is disabled with title 已在 watchlist', async () => {
    setupStore(SYMBOL)
    vi.mocked(getSignals).mockResolvedValue(signalsWith as never)
    renderWidget()

    await screen.findByTestId('price-chart')
    // Wait for signals query to resolve and button state to update
    await waitFor(() => {
      expect(screen.getByTitle('已在 watchlist')).toBeDisabled()
    })
  })
})

describe('T3 – click triggers addStock and shows pending state', () => {
  it('calls addStock(symbol) and button becomes disabled during pending', async () => {
    vi.mocked(addStock).mockImplementation(() => new Promise(() => {})) // never resolves
    setupStore(SYMBOL)
    renderWidget()

    await screen.findByTestId('price-chart')
    const btn = screen.getByTitle('添加到 watchlist')
    fireEvent.click(btn)

    // mutationFn is called asynchronously by react-query
    await waitFor(() => {
      expect(addStock).toHaveBeenCalledWith(SYMBOL)
      expect(btn).toBeDisabled()
    })
  })
})

describe('T4 – success invalidates signals and watchlist queries', () => {
  it('calls invalidateQueries for both query keys on success', async () => {
    vi.mocked(addStock).mockResolvedValue(undefined as never)
    setupStore(SYMBOL)

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    render(<QueryClientProvider client={qc}><ChartWidget /></QueryClientProvider>)

    await screen.findByTestId('price-chart')
    fireEvent.click(screen.getByTitle('添加到 watchlist'))

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['signals'] })
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['watchlist'] })
    })
  })
})

describe('T5 – DUPLICATE error shows 该股票已在 watchlist', () => {
  it('button title shows duplicate error message', async () => {
    vi.mocked(addStock).mockRejectedValue(new ApiError('DUPLICATE', 'already exists', 409))
    setupStore(SYMBOL)
    renderWidget()

    await screen.findByTestId('price-chart')
    fireEvent.click(screen.getByTitle('添加到 watchlist'))

    await waitFor(() => {
      expect(screen.getByTitle('该股票已在 watchlist')).toBeInTheDocument()
    })
  })
})

describe('T6 – NOT_FOUND error shows 股票代码无效', () => {
  it('button title shows not-found error message', async () => {
    vi.mocked(addStock).mockRejectedValue(new ApiError('NOT_FOUND', 'not found', 404))
    setupStore(SYMBOL)
    renderWidget()

    await screen.findByTestId('price-chart')
    fireEvent.click(screen.getByTitle('添加到 watchlist'))

    await waitFor(() => {
      expect(screen.getByTitle('股票代码无效')).toBeInTheDocument()
    })
  })
})

describe('T7 – symbol null → EmptySymbol, no button rendered', () => {
  it('shows EmptySymbol text and no add button', () => {
    setupStore(null)
    renderWidget()

    expect(screen.getByText('请在 Watchlist 中选择一只股票')).toBeInTheDocument()
    expect(screen.queryByTitle('添加到 watchlist')).not.toBeInTheDocument()
  })
})
