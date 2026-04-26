import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { PositionListWidget } from '../PositionListWidget'

// ── Mock data ──────────────────────────────────────────────────────────────────

const mockSummary = {
  openRiskPct: 2.5,
  totalExposurePct: 45.0,
  pendingRiskPct: 1.0,
  positionsCount: 5,
  pendingCount: 2,
}

const makePosition = (overrides = {}) => ({
  id: 1,
  ticker: 'NVDA',
  entryPrice: 850.0,
  entryDate: '2026-04-15',
  shares: 33,
  stopPrice: 820.0,
  target2r: 910.0,
  target3r: 940.0,
  setupType: 'BREAKOUT',
  status: 'OPEN',
  lastClose: 875.0,
  rMultiple: 0.83,
  unrealizedPl: 825.0,
  positionValue: 28875.0,
  earningsDate: '2026-05-22',
  daysUntilEarnings: 28,
  nextAction: 'hold',
  closedAt: null,
  closePrice: null,
  notes: null,
  createdAt: '2026-04-15T10:00:00Z',
  updatedAt: '2026-04-15T10:00:00Z',
  ...overrides,
})

function makeOkResponse(data: unknown) {
  return { ok: true, json: () => Promise.resolve({ data, message: 'success' }) }
}

function makePositionsFetch(items = [makePosition()], summary = mockSummary, statusOverride?: number) {
  return vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === 'PATCH') {
      const id = url.match(/positions\/(\d+)/)?.[1]
      return Promise.resolve(makeOkResponse({ ...makePosition(), id: Number(id) }))
    }
    if (init?.method === 'DELETE') {
      return Promise.resolve(makeOkResponse({ id: 1, deleted: true }))
    }
    if (statusOverride === 500) {
      return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: { code: 'SERVER_ERROR', message: 'fail' } }) })
    }
    return Promise.resolve(makeOkResponse({ summary, items }))
  }) as unknown as typeof fetch
}

function renderWidget() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
  render(<QueryClientProvider client={qc}><PositionListWidget /></QueryClientProvider>)
  return { qc, invalidateSpy }
}

beforeEach(() => { vi.stubGlobal('fetch', makePositionsFetch()) })
afterEach(() => vi.unstubAllGlobals())

// ── S5 – Summary bar ───────────────────────────────────────────────────────────

describe('S5 – summary bar renders 5 fields', () => {
  it('renders all 5 summary values', async () => {
    renderWidget()
    await waitFor(() => {
      expect(screen.getByText('Open Risk: 2.5%')).toBeInTheDocument()
      expect(screen.getByText('Exposure: 45%')).toBeInTheDocument()
      expect(screen.getByText('Pending: 1.0%')).toBeInTheDocument()
      expect(screen.getByText('5 pos')).toBeInTheDocument()
      expect(screen.getByText('2 ord')).toBeInTheDocument()
    })
  })
})

// ── S6 – Items render ──────────────────────────────────────────────────────────

describe('S6 – position row renders required fields', () => {
  it('renders ticker, entry, last, stop, rMultiple, pl, earnings, nextAction', async () => {
    renderWidget()
    await waitFor(() => {
      expect(screen.getByText('NVDA')).toBeInTheDocument()
      expect(screen.getByText('850.00')).toBeInTheDocument()  // entry
      expect(screen.getByText('875.00')).toBeInTheDocument()  // last
      expect(screen.getByText('820.00')).toBeInTheDocument()  // stop
      expect(screen.getByText('0.83')).toBeInTheDocument()    // rMultiple
      expect(screen.getByText('+$825')).toBeInTheDocument()   // pl
      expect(screen.getByTestId('next-action-chip-1')).toBeInTheDocument()
    })
    // EarningsRiskDot renders a dot span (daysUntilEarnings=28 → SAFE)
    expect(screen.getByTestId('risk-summary-bar')).toBeInTheDocument()
  })
})

// ── S7 – rMultiple positive/negative color ─────────────────────────────────────

describe('S7 – rMultiple color', () => {
  it('positive rMultiple → change-positive color token', async () => {
    renderWidget()
    await waitFor(() => expect(screen.getByText('0.83')).toBeInTheDocument())
    const cell = screen.getByText('0.83')
    expect(cell.getAttribute('style') ?? '').toContain('--color-change-positive')
  })

  it('negative rMultiple → change-negative color token', async () => {
    vi.stubGlobal('fetch', makePositionsFetch([makePosition({ rMultiple: -0.50, unrealizedPl: -140 })]))
    renderWidget()
    await waitFor(() => expect(screen.getByText('-0.50')).toBeInTheDocument())
    const cell = screen.getByText('-0.50')
    expect(cell.getAttribute('style') ?? '').toContain('--color-change-negative')
  })
})

// ── S8 – nextAction chip colors ────────────────────────────────────────────────

describe('S8 – nextAction 4-state chip colors', () => {
  const cases: Array<[string, string, string]> = [
    ['hold', 'Watch', '--color-action-watch'],
    ['raise_stop', 'Add', '--color-action-add'],
    ['reduce', 'Reduce', '--color-action-reduce'],
    ['exit', 'Sell', '--color-action-sell'],
  ]

  it.each(cases)('nextAction=%s → label=%s, color contains %s', async (action, label, token) => {
    vi.stubGlobal('fetch', makePositionsFetch([makePosition({ nextAction: action, id: 1 })]))
    renderWidget()
    await waitFor(() => expect(screen.getByTestId('next-action-chip-1')).toBeInTheDocument())
    const chip = screen.getByTestId('next-action-chip-1')
    expect(chip.textContent).toBe(label)
    expect(chip.getAttribute('style') ?? '').toContain(token)
  })
})

// ── S9 – Status filter ────────────────────────────────────────────────────────

describe('S9 – status filter changes query', () => {
  it('[Closed] → refetch with status=closed in URL', async () => {
    const fetchMock = makePositionsFetch()
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await waitFor(() => expect(screen.getByText('NVDA')).toBeInTheDocument())

    fireEvent.click(screen.getByText('Closed'))

    await waitFor(() => {
      const urls = (fetchMock as ReturnType<typeof vi.fn>).mock.calls.map((c: [string]) => c[0])
      expect(urls.some((u) => u.includes('status=closed'))).toBe(true)
    })
  })

  it('[All] → refetch with status=all in URL', async () => {
    const fetchMock = makePositionsFetch()
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await waitFor(() => expect(screen.getByText('NVDA')).toBeInTheDocument())

    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      const urls = (fetchMock as ReturnType<typeof vi.fn>).mock.calls.map((c: [string]) => c[0])
      expect(urls.some((u) => u.includes('status=all'))).toBe(true)
    })
  })
})

// ── S10 – Empty & error states ────────────────────────────────────────────────

describe('S10 – empty and error states', () => {
  it('items=[] → shows "暂无持仓"', async () => {
    vi.stubGlobal('fetch', makePositionsFetch([]))
    renderWidget()
    await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument())
    expect(screen.getByText('暂无持仓')).toBeInTheDocument()
  })

  it('fetch error → shows error banner', async () => {
    vi.stubGlobal('fetch', makePositionsFetch([], mockSummary, 500))
    renderWidget()
    await waitFor(() => expect(screen.getByTestId('error-banner')).toBeInTheDocument())
  })
})

// ── S11 – Row expand + PATCH ──────────────────────────────────────────────────

describe('S11 – row expand → inline form → PATCH + invalidate', () => {
  it('click row → inline form appears; save → PATCH called; invalidate cockpit-positions', async () => {
    const fetchMock = makePositionsFetch()
    vi.stubGlobal('fetch', fetchMock)
    const { qc } = renderWidget()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    await waitFor(() => expect(screen.getByText('NVDA')).toBeInTheDocument())

    // Click row to expand
    fireEvent.click(screen.getByText('NVDA'))

    await waitFor(() => {
      expect(screen.getByLabelText('Stop price')).toBeInTheDocument()
      expect(screen.getByLabelText('Status')).toBeInTheDocument()
      expect(screen.getByLabelText('Notes')).toBeInTheDocument()
    })

    // Change stop price
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '830' } })

    // Save
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      const patchCalls = (fetchMock as ReturnType<typeof vi.fn>).mock.calls.filter(
        (c: [string, RequestInit]) => c[1]?.method === 'PATCH',
      )
      expect(patchCalls.length).toBe(1)
      expect(patchCalls[0][0]).toContain('/cockpit/positions/1')
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-positions'] }),
      )
    })
  })
})

// ── S12 – Delete confirm flow ─────────────────────────────────────────────────

describe('S12 – delete AlertDialog confirm/cancel', () => {
  it('confirm → DELETE called + invalidate; cancel → no DELETE', async () => {
    const fetchMock = makePositionsFetch()
    vi.stubGlobal('fetch', fetchMock)
    const { qc } = renderWidget()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    await waitFor(() => expect(screen.getByTestId('delete-btn-1')).toBeInTheDocument())

    // Open AlertDialog
    fireEvent.click(screen.getByTestId('delete-btn-1'))

    await waitFor(() => expect(screen.getByText('确认删除')).toBeInTheDocument())

    // Cancel → no DELETE
    fireEvent.click(screen.getByText('取消'))
    expect((fetchMock as ReturnType<typeof vi.fn>).mock.calls.filter(
      (c: [string, RequestInit]) => c[1]?.method === 'DELETE',
    ).length).toBe(0)

    // Reopen and confirm
    fireEvent.click(screen.getByTestId('delete-btn-1'))
    await waitFor(() => expect(screen.getByText('删除')).toBeInTheDocument())
    fireEvent.click(screen.getByText('删除'))

    await waitFor(() => {
      const delCalls = (fetchMock as ReturnType<typeof vi.fn>).mock.calls.filter(
        (c: [string, RequestInit]) => c[1]?.method === 'DELETE',
      )
      expect(delCalls.length).toBe(1)
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-positions'] }),
      )
    })
  })
})

// ── S13 – New Position dialog ─────────────────────────────────────────────────

describe('S13 – [+ New Position] opens PositionFormDialog mode=new', () => {
  it('button click → dialog opens with "New Position" title', async () => {
    renderWidget()
    await waitFor(() => expect(screen.getByText('NVDA')).toBeInTheDocument())

    fireEvent.click(screen.getByText('+ New Position'))

    await waitFor(() => expect(screen.getByText('New Position')).toBeInTheDocument())
  })
})
