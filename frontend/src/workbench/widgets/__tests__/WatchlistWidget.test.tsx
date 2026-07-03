import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { toast } from 'sonner'
import { WatchlistWidget } from '../WatchlistWidget'
import { ApiError } from '@/lib/api/client'
import { useAppStore } from '@/store/useAppStore'
import { getSignals } from '@/lib/api/signals'
import { updateColor } from '@/lib/api/watchlist'
import type { SignalBoardItem } from '@/types/signal'

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('@/store/useAppStore', () => ({ useAppStore: vi.fn() }))
vi.mock('@/lib/api/signals', () => ({ getSignals: vi.fn() }))
vi.mock('@/lib/api/watchlist', () => ({
  removeStock: vi.fn(),
  updateColor: vi.fn(),
}))
vi.mock('sonner', () => ({ toast: vi.fn() }))
vi.mock('@/components/features/dashboard/AddStockCard', () => ({
  AddStockCard: () => null,
}))
vi.mock('@/components/features/dashboard/CsvImportDialog', () => ({
  CsvImportDialog: () => null,
}))

// ── Helpers ────────────────────────────────────────────────────────────────

const STOCK_NULL: SignalBoardItem = {
  ticker: 'AAPL',
  name: 'Apple Inc.',
  signalType: 'NEUTRAL',
  date: '2026-07-01',
  closePrice: 200,
  ma150Value: 190,
  distancePct: 5,
  slopePositive: true,
  slopeValue: 0.1,
  labelColor: null,
}

const STOCK_RED: SignalBoardItem = {
  ...STOCK_NULL,
  ticker: 'MSFT',
  name: 'Microsoft Corporation',
  labelColor: 'red',
}

function setupStore() {
  const setSelectedSymbol = vi.fn()
  vi.mocked(useAppStore).mockImplementation(
    (selector: (s: { setSelectedSymbol: typeof setSelectedSymbol }) => unknown) =>
      selector({ setSelectedSymbol }),
  )
  return { setSelectedSymbol }
}

function renderWidget() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return { qc, ...render(<QueryClientProvider client={qc}><WatchlistWidget /></QueryClientProvider>) }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getSignals).mockResolvedValue([STOCK_NULL, STOCK_RED])
})

describe('TC1 – null labelColor renders hollow ring trigger', () => {
  it('renders transparent background with border', async () => {
    setupStore()
    renderWidget()

    const btn = await screen.findByLabelText('颜色标记 AAPL')
    expect(btn.style.backgroundColor).toBe('transparent')
    expect(btn.style.border).toContain('1.5px solid')
  })
})

describe('TC2 – red labelColor renders solid trigger', () => {
  it('renders filled background with no border', async () => {
    setupStore()
    renderWidget()

    const btn = await screen.findByLabelText('颜色标记 MSFT')
    expect(btn.style.backgroundColor).toBe('var(--color-label-red)')
    expect(btn.style.borderStyle).toBe('none')
  })
})

describe('TC3 – click trigger opens Popover with 4 swatches', () => {
  it('shows red/yellow/blue/clear buttons', async () => {
    setupStore()
    renderWidget()

    const btn = await screen.findByLabelText('颜色标记 AAPL')
    fireEvent.click(btn)

    expect(await screen.findByLabelText('标记红色')).toBeInTheDocument()
    expect(screen.getByLabelText('标记黄色')).toBeInTheDocument()
    expect(screen.getByLabelText('标记蓝色')).toBeInTheDocument()
    expect(screen.getByLabelText('清除标记')).toBeInTheDocument()
  })
})

describe('TC4 – selecting a swatch calls updateColor and closes Popover', () => {
  it('calls updateColor(ticker, "red") and popover closes', async () => {
    vi.mocked(updateColor).mockResolvedValue({ ticker: 'AAPL', labelColor: 'red' })
    setupStore()
    renderWidget()

    fireEvent.click(await screen.findByLabelText('颜色标记 AAPL'))
    fireEvent.click(await screen.findByLabelText('标记红色'))

    await waitFor(() => {
      expect(updateColor).toHaveBeenCalledWith('AAPL', 'red')
    })
    await waitFor(() => {
      expect(screen.queryByLabelText('标记红色')).not.toBeInTheDocument()
    })
  })
})

describe('TC5 – clicking trigger or swatch does not select the row', () => {
  it('setSelectedSymbol is never called', async () => {
    vi.mocked(updateColor).mockResolvedValue({ ticker: 'AAPL', labelColor: 'red' })
    const { setSelectedSymbol } = setupStore()
    renderWidget()

    fireEvent.click(await screen.findByLabelText('颜色标记 AAPL'))
    fireEvent.click(await screen.findByLabelText('标记红色'))

    await waitFor(() => {
      expect(updateColor).toHaveBeenCalled()
    })
    expect(setSelectedSymbol).not.toHaveBeenCalled()
  })
})

describe('TC6 – updateColor success invalidates signals query', () => {
  it('refetches signals after success', async () => {
    vi.mocked(updateColor).mockResolvedValue({ ticker: 'AAPL', labelColor: 'red' })
    setupStore()

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    render(<QueryClientProvider client={qc}><WatchlistWidget /></QueryClientProvider>)

    fireEvent.click(await screen.findByLabelText('颜色标记 AAPL'))
    fireEvent.click(await screen.findByLabelText('标记红色'))

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['signals'] })
    })
  })
})

describe('TC7 – NOT_FOUND error silently invalidates, no toast', () => {
  it('invalidates without calling toast', async () => {
    vi.mocked(updateColor).mockRejectedValue(new ApiError('NOT_FOUND', 'gone', 404))
    setupStore()

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    render(<QueryClientProvider client={qc}><WatchlistWidget /></QueryClientProvider>)

    fireEvent.click(await screen.findByLabelText('颜色标记 AAPL'))
    fireEvent.click(await screen.findByLabelText('标记红色'))

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['signals'] })
    })
    expect(toast).not.toHaveBeenCalled()
  })
})

describe('TC8 – other errors show a toast', () => {
  it('calls toast on non-NOT_FOUND error', async () => {
    vi.mocked(updateColor).mockRejectedValue(new ApiError('VALIDATION_ERROR', 'bad', 422))
    setupStore()
    renderWidget()

    fireEvent.click(await screen.findByLabelText('颜色标记 AAPL'))
    fireEvent.click(await screen.findByLabelText('标记红色'))

    await waitFor(() => {
      expect(toast).toHaveBeenCalledWith('颜色标记更新失败，请重试')
    })
  })
})

describe('TC9 – CSV export includes color column', () => {
  it('generates ticker,name,color rows with null → none', async () => {
    let exportedText = ''
    const originalCreateObjectURL = URL.createObjectURL
    const originalRevokeObjectURL = URL.revokeObjectURL
    URL.createObjectURL = vi.fn((blob: Blob) => {
      void blob.text().then((t) => { exportedText = t })
      return 'blob:mock'
    })
    URL.revokeObjectURL = vi.fn()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    setupStore()
    renderWidget()

    await screen.findByLabelText('颜色标记 AAPL')
    fireEvent.click(screen.getByTitle('导出 CSV'))

    await waitFor(() => {
      expect(exportedText).toContain('ticker,name,color')
    })
    expect(exportedText).toContain('AAPL,"Apple Inc.",none')
    expect(exportedText).toContain('MSFT,"Microsoft Corporation",red')

    clickSpy.mockRestore()
    URL.createObjectURL = originalCreateObjectURL
    URL.revokeObjectURL = originalRevokeObjectURL
  })
})
