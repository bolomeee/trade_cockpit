import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { PendingOrdersWidget } from '../PendingOrdersWidget'
import type { PendingOrder } from '../../lib/api/cockpitPendingOrdersApi'

// ── mocks ─────────────────────────────────────────────────────────────────────

vi.mock('sonner', () => ({ toast: vi.fn() }))

// ── helpers ───────────────────────────────────────────────────────────────────

function makeOrder(overrides: Partial<PendingOrder> = {}): PendingOrder {
  return {
    id: 1,
    ticker: 'NVDA',
    setupType: 'BREAKOUT',
    entryPrice: 900.0,
    stopPrice: 860.0,
    shares: 20,
    target2r: null,
    target3r: null,
    expirationDate: '2026-06-30',
    status: 'ACTIVE',
    lastClose: 870.0,
    distanceToTriggerPct: 3.45,
    riskPct: 1.5,
    notes: null,
    createdAt: '2026-04-20T10:00:00Z',
    updatedAt: '2026-04-20T10:00:00Z',
    ...overrides,
  }
}

function makeOkResponse(data: unknown) {
  return { ok: true, json: () => Promise.resolve({ data, message: 'success' }) }
}

function makeOrdersFetch(orders: PendingOrder[] = [makeOrder()], statusCode = 200) {
  return vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === 'PATCH') {
      const id = url.match(/pending-orders\/(\d+)/)?.[1]
      return Promise.resolve(makeOkResponse({ ...makeOrder(), id: Number(id) }))
    }
    if (init?.method === 'DELETE') {
      return Promise.resolve(makeOkResponse({ id: 1, deleted: true }))
    }
    if (statusCode === 500) {
      return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: { code: 'SERVER_ERROR', message: 'fail' } }) })
    }
    return Promise.resolve(makeOkResponse(orders))
  }) as unknown as typeof fetch
}

function renderWidget(fetchFn?: typeof fetch) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
  if (fetchFn) vi.stubGlobal('fetch', fetchFn)
  render(<QueryClientProvider client={qc}><PendingOrdersWidget /></QueryClientProvider>)
  return { qc, invalidateSpy }
}

beforeEach(() => vi.stubGlobal('fetch', makeOrdersFetch()))
afterEach(() => vi.unstubAllGlobals())

// ── S5 table headers ──────────────────────────────────────────────────────────

describe('S5 – table headers render', () => {
  it('renders all 8 column headers in order', async () => {
    renderWidget()
    await waitFor(() => expect(screen.getByText('NVDA')).toBeInTheDocument())
    const headers = ['Ticker', 'Setup', 'Entry', 'Stop', 'Last', 'Dist', 'Risk%', 'Exp']
    const ths = screen.getAllByRole('columnheader')
    expect(ths).toHaveLength(headers.length)
    headers.forEach((h, i) => expect(ths[i].textContent).toBe(h))
  })

  it('renders SetupTypeBadge in Setup column', async () => {
    renderWidget()
    await waitFor(() => expect(screen.getByText('BREAKOUT')).toBeInTheDocument())
  })
})

// ── S7 status toggle ──────────────────────────────────────────────────────────

describe('S7 – Active↔All toggle refetches', () => {
  it('[All] → refetch with status=all in URL', async () => {
    const fetchMock = makeOrdersFetch()
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await waitFor(() => expect(screen.getByText('NVDA')).toBeInTheDocument())

    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      const urls = (fetchMock as ReturnType<typeof vi.fn>).mock.calls.map((c: [string]) => c[0])
      expect(urls.some((u: string) => u.includes('status=all'))).toBe(true)
    })
  })

  it('[Active] → default URL uses status=active', async () => {
    const fetchMock = makeOrdersFetch()
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await waitFor(() => expect(screen.getByText('NVDA')).toBeInTheDocument())
    const urls = (fetchMock as ReturnType<typeof vi.fn>).mock.calls.map((c: [string]) => c[0])
    expect(urls.some((u: string) => u.includes('status=active'))).toBe(true)
  })
})

// ── S9 Triggered confirm flow + toast ────────────────────────────────────────

describe('S9 – Triggered AlertDialog + PATCH status=TRIGGERED + toast', () => {
  it('confirm → PATCH TRIGGERED + invalidate pending-orders (not positions) + toast', async () => {
    const { toast } = await import('sonner')
    const fetchMock = makeOrdersFetch([makeOrder({ id: 1, status: 'ACTIVE' })])
    vi.stubGlobal('fetch', fetchMock)
    const { qc } = renderWidget()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    await waitFor(() => expect(screen.getByTestId('triggered-btn-1')).toBeInTheDocument())

    fireEvent.click(screen.getByTestId('triggered-btn-1'))
    await waitFor(() => expect(screen.getByText('确认')).toBeInTheDocument())
    fireEvent.click(screen.getByText('确认'))

    await waitFor(() => {
      const patchCalls = (fetchMock as ReturnType<typeof vi.fn>).mock.calls.filter(
        (c) => c[1]?.method === 'PATCH',
      )
      expect(patchCalls).toHaveLength(1)
      const body = JSON.parse(patchCalls[0][1].body as string)
      expect(body.status).toBe('TRIGGERED')
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-pending-orders'] }),
      )
    })

    // Verify NOT invalidating cockpit-positions (D060-a)
    const positionInvalidations = (invalidateSpy.mock.calls as Array<[{ queryKey: string[] }]>).filter(
      (c) => c[0]?.queryKey?.[0] === 'cockpit-positions',
    )
    expect(positionInvalidations).toHaveLength(0)

    expect(toast).toHaveBeenCalledWith(expect.stringContaining('TRIGGERED'))
  })
})

// ── S12 Delete confirm flow ───────────────────────────────────────────────────

describe('S12 – Delete AlertDialog confirm/cancel', () => {
  it('cancel → no DELETE called', async () => {
    const fetchMock = makeOrdersFetch()
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await waitFor(() => expect(screen.getByTestId('delete-btn-1')).toBeInTheDocument())

    fireEvent.click(screen.getByTestId('delete-btn-1'))
    await waitFor(() => expect(screen.getByText('确认删除')).toBeInTheDocument())
    fireEvent.click(screen.getByText('取消'))

    expect((fetchMock as ReturnType<typeof vi.fn>).mock.calls.filter(
      (c) => c[1]?.method === 'DELETE',
    )).toHaveLength(0)
  })

  it('confirm → DELETE called + invalidate', async () => {
    const fetchMock = makeOrdersFetch()
    vi.stubGlobal('fetch', fetchMock)
    const { qc } = renderWidget()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    await waitFor(() => expect(screen.getByTestId('delete-btn-1')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('delete-btn-1'))
    await waitFor(() => expect(screen.getByText('删除')).toBeInTheDocument())
    fireEvent.click(screen.getByText('删除'))

    await waitFor(() => {
      expect((fetchMock as ReturnType<typeof vi.fn>).mock.calls.filter(
        (c) => c[1]?.method === 'DELETE',
      )).toHaveLength(1)
    })
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-pending-orders'] }),
      )
    })
  })
})

// ── S13 empty + error states ──────────────────────────────────────────────────

describe('S13 – empty and error states', () => {
  it('items=[] → shows "暂无 pending order"', async () => {
    vi.stubGlobal('fetch', makeOrdersFetch([]))
    renderWidget()
    await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument())
    expect(screen.getByText('暂无 pending order')).toBeInTheDocument()
  })

  it('fetch error → shows error banner', async () => {
    vi.stubGlobal('fetch', makeOrdersFetch([], 500))
    renderWidget()
    await waitFor(() => expect(screen.getByTestId('error-banner')).toBeInTheDocument())
  })
})

// ── S14 New Order dialog ──────────────────────────────────────────────────────

describe('S14 – [+ New Order] opens PendingOrderFormDialog mode=new', () => {
  it('click [+ New Order] → dialog opens with "New Pending Order" title', async () => {
    renderWidget()
    await waitFor(() => expect(screen.getByText('NVDA')).toBeInTheDocument())
    fireEvent.click(screen.getByText('+ New Order'))
    await waitFor(() => expect(screen.getByText('New Pending Order')).toBeInTheDocument())
  })
})
