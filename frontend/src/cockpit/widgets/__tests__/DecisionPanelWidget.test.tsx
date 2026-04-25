import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { DecisionPanelWidget } from '../DecisionPanelWidget'
import { useCockpitStore } from '@/store/cockpitStore'

// ── Mock data ──────────────────────────────────────────────────────────────────

const mockDecision = {
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
  deterministicHash: 'abc123de456789',
}

function makeDecisionFetch(status?: 200 | 404 | 422) {
  return vi.fn((url: string) => {
    if (!url.includes('/cockpit/decision/')) {
      return Promise.reject(new Error(`Unexpected URL: ${url}`))
    }
    if (status === 404) {
      return Promise.resolve({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: { code: 'NOT_FOUND', message: 'not found' } }),
      })
    }
    if (status === 422) {
      return Promise.resolve({
        ok: false,
        status: 422,
        json: () =>
          Promise.resolve({
            error: { code: 'VALIDATION_ERROR', message: 'entry must be > stop' },
          }),
      })
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ data: mockDecision }),
    })
  }) as unknown as typeof fetch
}

function renderWidget() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <DecisionPanelWidget />
    </QueryClientProvider>,
  )
}

// ── Setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  useCockpitStore.setState({ selectedTicker: null })
})

afterEach(() => {
  useCockpitStore.setState({ selectedTicker: null })
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('S3 – empty state when no ticker', () => {
  it('shows empty prompt and makes no fetch', () => {
    vi.stubGlobal('fetch', vi.fn())
    renderWidget()
    expect(screen.getByText('请在 Setup Monitor 或 Chart 选择一只股票')).toBeInTheDocument()
    expect(global.fetch).not.toHaveBeenCalled()
  })
})

describe('S4 – ticker NVDA → loading → renders all decision fields', () => {
  it('shows header with BREAKOUT then renders all required fields', async () => {
    vi.stubGlobal('fetch', makeDecisionFetch())
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    // Header should show ticker immediately
    expect(screen.getByText(/Decision · NVDA/)).toBeInTheDocument()

    // Wait for data to render
    await waitFor(() => {
      expect(screen.getByText(/Decision.*BREAKOUT.*A/)).toBeInTheDocument()
    })

    // Decision Card fields
    expect(screen.getByText('850.00')).toBeInTheDocument()
    expect(screen.getByText('820.00')).toBeInTheDocument()
    expect(screen.getByText('910.00')).toBeInTheDocument()
    expect(screen.getByText('940.00')).toBeInTheDocument()
    expect(screen.getByText('33 shares')).toBeInTheDocument()
    expect(screen.getByText('0.99%')).toBeInTheDocument()
    expect(screen.getByText('Effective Risk%')).toBeInTheDocument()
    expect(screen.getByText('1.00%')).toBeInTheDocument()
    // Hash (first 8 chars + ellipsis)
    expect(screen.getByText('abc123de…')).toBeInTheDocument()
    // Override form inputs rendered
    const inputs = screen.getAllByPlaceholderText('—')
    expect(inputs.length).toBe(3)
  })
})

describe('S5 – override input debounce 500ms', () => {
  it('does not refetch before 500ms, refetches after with entryOverride in URL', async () => {
    vi.useFakeTimers()
    const fetchMock = makeDecisionFetch()
    vi.stubGlobal('fetch', fetchMock)
    useCockpitStore.setState({ selectedTicker: 'NVDA' })

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <DecisionPanelWidget />
      </QueryClientProvider>,
    )

    // Let the initial fetch fire and resolve (Promises still work with fake timers)
    await vi.waitFor(async () => {
      expect(fetchMock.mock.calls.length).toBeGreaterThan(0)
    })

    // Manually advance react-query to process the resolved promise
    await vi.waitFor(() => {
      expect(screen.queryAllByPlaceholderText('—').length).toBe(3)
    })

    const callsAfterInit = fetchMock.mock.calls.length

    // Type in first override input (Entry override)
    const inputs = screen.getAllByPlaceholderText('—')
    fireEvent.change(inputs[0], { target: { value: '855' } })

    // 499ms: no additional fetch
    vi.advanceTimersByTime(499)
    expect(fetchMock.mock.calls.length).toBe(callsAfterInit)

    // 500ms: debounce fires → state update → queryKey change → refetch
    vi.advanceTimersByTime(1)
    await vi.waitFor(() => {
      const allUrls = fetchMock.mock.calls.map((c) => c[0] as string)
      expect(allUrls.some((u) => u.includes('entryOverride=855'))).toBe(true)
    })
  })
})

describe('S6 – Recompute button triggers immediate refetch', () => {
  it('clicking Recompute calls refetch without waiting for debounce', async () => {
    const fetchMock = makeDecisionFetch()
    vi.stubGlobal('fetch', fetchMock)
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    // Wait for initial data and override form to be rendered
    await waitFor(() => {
      expect(screen.getAllByPlaceholderText('—').length).toBe(3)
    })

    const callsAfterInit = fetchMock.mock.calls.length

    // Click Recompute immediately
    const recomputeBtn = screen.getByText('↻ Recompute')
    fireEvent.click(recomputeBtn)

    // Should have refetched immediately (without waiting 500ms)
    await waitFor(() => {
      expect(fetchMock.mock.calls.length).toBeGreaterThan(callsAfterInit)
    })
  })
})

describe('S7 – decision 404 → error message + override form still active', () => {
  it('shows 404 message and override inputs remain interactive', async () => {
    vi.stubGlobal('fetch', makeDecisionFetch(404))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByText('无 setup 数据，可手动 override entry/stop')).toBeInTheDocument()
    })

    // Override form inputs should be present and interactable
    const inputs = screen.getAllByPlaceholderText('—')
    expect(inputs.length).toBe(3)
    fireEvent.change(inputs[0], { target: { value: '840' } })
    expect((inputs[0] as HTMLInputElement).value).toBe('840')
  })
})

describe('S8 – decision 422 → red error message', () => {
  it('shows red "entry 必须大于 stop" error', async () => {
    vi.stubGlobal('fetch', makeDecisionFetch(422))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByText('entry 必须大于 stop')).toBeInTheDocument()
    })
  })
})

describe('S17 – Save as PendingOrder button is disabled', () => {
  it('button exists, is disabled, clicking triggers no fetch', async () => {
    vi.stubGlobal('fetch', makeDecisionFetch())
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText('—').length).toBe(3)
    })

    const btn = screen.getByText('📋 Save as PendingOrder').closest('button')!
    expect(btn).toBeDisabled()

    const callsBefore = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.length
    fireEvent.click(btn)
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(callsBefore)
  })
})
