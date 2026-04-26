import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { PositionFormDialog } from '../PositionFormDialog'
import { useCockpitStore } from '@/store/cockpitStore'

// ── Mock data ──────────────────────────────────────────────────────────────────

const mockPosition = {
  id: 1,
  ticker: 'NVDA',
  entryPrice: 850.0,
  entryDate: '2026-04-15',
  shares: 33,
  stopPrice: 820.0,
  target2r: 910.0,
  target3r: 940.0,
  setupType: 'BREAKOUT',
  status: 'OPEN' as const,
  lastClose: 875.0,
  rMultiple: 0.83,
  unrealizedPl: 825.0,
  positionValue: 28875.0,
  earningsDate: '2026-05-22',
  daysUntilEarnings: 28,
  nextAction: 'hold' as const,
  closedAt: null,
  closePrice: null,
  notes: null,
  createdAt: '2026-04-15T10:00:00Z',
  updatedAt: '2026-04-15T10:00:00Z',
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

function makeOkResponse(data: unknown, status = 200) {
  return Promise.resolve({ ok: true, status, json: () => Promise.resolve({ data, message: 'success' }) })
}

function renderNewDialog(qc?: QueryClient) {
  const client = qc ?? new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
  const onSaved = vi.fn()
  const onClose = vi.fn()
  render(
    <QueryClientProvider client={client}>
      <PositionFormDialog mode="new" open onSaved={onSaved} onClose={onClose} />
    </QueryClientProvider>,
  )
  return { client, invalidateSpy, onSaved, onClose }
}

function renderEditDialog(position = mockPosition, qc?: QueryClient) {
  const client = qc ?? new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
  const onSaved = vi.fn()
  const onClose = vi.fn()
  render(
    <QueryClientProvider client={client}>
      <PositionFormDialog mode="edit" open onSaved={onSaved} onClose={onClose} initialPosition={position} />
    </QueryClientProvider>,
  )
  return { client, invalidateSpy, onSaved, onClose }
}

// ── Setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  useCockpitStore.setState({ selectedTicker: null })
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  useCockpitStore.setState({ selectedTicker: null })
  vi.unstubAllGlobals()
})

// ── S14 – Validation failures ─────────────────────────────────────────────────

describe('S14 – new mode validation failures', () => {
  it('ticker empty → shows error, no POST', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderNewDialog()

    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '850' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '820' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '33' } })

    await userEvent.setup().click(screen.getByText('Add Position'))

    await waitFor(() => {
      expect(screen.getByText('Ticker required')).toBeInTheDocument()
    })
    const postCalls = fetchMock.mock.calls.filter((c: [string, RequestInit]) => c[1]?.method === 'POST')
    expect(postCalls.length).toBe(0)
  })

  it('entryPrice ≤ 0 → shows error, no POST', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderNewDialog()

    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '0' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '820' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '33' } })

    await userEvent.setup().click(screen.getByText('Add Position'))

    await waitFor(() => {
      expect(screen.getAllByText('Must be > 0').length).toBeGreaterThan(0)
    })
    expect(fetchMock.mock.calls.filter((c: [string, RequestInit]) => c[1]?.method === 'POST').length).toBe(0)
  })

  it('stopPrice ≤ 0 → shows error, no POST', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderNewDialog()

    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '850' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '0' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '33' } })

    await userEvent.setup().click(screen.getByText('Add Position'))

    await waitFor(() => {
      expect(screen.getAllByText('Must be > 0').length).toBeGreaterThan(0)
    })
    expect(fetchMock.mock.calls.filter((c: [string, RequestInit]) => c[1]?.method === 'POST').length).toBe(0)
  })

  it('entryPrice ≤ stopPrice → shows error, no POST', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderNewDialog()

    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '820' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '820' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '33' } })

    await userEvent.setup().click(screen.getByText('Add Position'))

    await waitFor(() => {
      expect(screen.getByText('Entry must be > stop')).toBeInTheDocument()
    })
    expect(fetchMock.mock.calls.filter((c: [string, RequestInit]) => c[1]?.method === 'POST').length).toBe(0)
  })

  it('shares ≤ 0 → shows error, no POST', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderNewDialog()

    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '850' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '820' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '0' } })

    await userEvent.setup().click(screen.getByText('Add Position'))

    await waitFor(() => {
      expect(screen.getAllByText('Must be > 0').length).toBeGreaterThan(0)
    })
    expect(fetchMock.mock.calls.filter((c: [string, RequestInit]) => c[1]?.method === 'POST').length).toBe(0)
  })
})

// ── S15 – Valid new submission ─────────────────────────────────────────────────

describe('S15 – new mode valid submit → POST camelCase body + invalidate', () => {
  it('POST body has camelCase fields; success → invalidate cockpit-positions + onSaved called', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeOkResponse(mockPosition, 201)),
    )
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    const onSaved = vi.fn()

    render(
      <QueryClientProvider client={qc}>
        <PositionFormDialog mode="new" open onSaved={onSaved} onClose={vi.fn()} />
      </QueryClientProvider>,
    )

    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '850' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '820' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '33' } })

    await userEvent.setup().click(screen.getByText('Add Position'))

    await waitFor(() => {
      const postCalls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
        (c: [string, RequestInit]) => c[1]?.method === 'POST',
      )
      expect(postCalls.length).toBe(1)
      const body = JSON.parse(postCalls[0][1].body as string)
      expect(body.ticker).toBe('NVDA')
      expect(body.entryPrice).toBe(850)
      expect(body.stopPrice).toBe(820)
      expect(body.shares).toBe(33)
      expect(body).not.toHaveProperty('entry_price')
      expect(body).not.toHaveProperty('stop_price')
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-positions'] }),
      )
    })

    expect(onSaved).toHaveBeenCalled()
  })
})

// ── S16 – Edit mode ───────────────────────────────────────────────────────────

describe('S16 – edit mode: pre-fills initialPosition + PATCH on submit', () => {
  it('pre-fills stop price from position; submit calls PATCH', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeOkResponse(mockPosition)),
    )
    const { invalidateSpy, onSaved } = renderEditDialog()

    const stopInput = screen.getByLabelText('Stop price') as HTMLInputElement
    expect(stopInput.value).toBe('820')

    fireEvent.change(stopInput, { target: { value: '840' } })

    await userEvent.setup().click(screen.getByText('Save'))

    await waitFor(() => {
      const patchCalls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
        (c: [string, RequestInit]) => c[1]?.method === 'PATCH',
      )
      expect(patchCalls.length).toBe(1)
      expect(patchCalls[0][0]).toContain('/cockpit/positions/1')
      const body = JSON.parse(patchCalls[0][1].body as string)
      expect(body.stopPrice).toBe(840)
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-positions'] }),
      )
    })

    expect(onSaved).toHaveBeenCalled()
  })
})

// ── S17 – suggestedShares hint ─────────────────────────────────────────────────

describe('S17 – suggestedShares hint', () => {
  it('shows hint when selectedTicker set and decision cached with suggestedShares=33', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    qc.setQueryData(['cockpit-decision', 'NVDA'], mockDecisionData)
    useCockpitStore.setState({ selectedTicker: 'NVDA' })

    renderNewDialog(qc)

    expect(screen.getByTestId('suggested-shares-hint')).toBeInTheDocument()
    expect(screen.getByTestId('suggested-shares-hint').textContent).toContain('Cockpit 推荐 33 shares')
  })

  it('does not show hint when selectedTicker is null', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    useCockpitStore.setState({ selectedTicker: null })

    renderNewDialog(qc)

    expect(screen.queryByTestId('suggested-shares-hint')).not.toBeInTheDocument()
  })

  it('does not show hint when no decision data cached', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    useCockpitStore.setState({ selectedTicker: 'NVDA' })

    renderNewDialog(qc)

    expect(screen.queryByTestId('suggested-shares-hint')).not.toBeInTheDocument()
  })
})
