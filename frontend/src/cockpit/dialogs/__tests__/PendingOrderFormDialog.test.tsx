import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock shadcn Select with native <select> so JSDOM form interactions work.
// This tests form logic and mutation behavior, not the Radix Select widget.
vi.mock('@/components/ui/select', () => ({
  Select: ({ value, onValueChange, children }: { value: string; onValueChange: (v: string) => void; children: React.ReactNode }) => (
    <select data-testid="native-select" value={value} onChange={(e) => onValueChange(e.target.value)}>
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: { children: React.ReactNode; id?: string }) => <>{children}</>,
  SelectValue: ({ placeholder }: { placeholder?: string }) => <option value="">{placeholder}</option>,
  SelectContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectItem: ({ value, children }: { value: string; children: React.ReactNode }) => (
    <option value={value}>{children}</option>
  ),
}))

import { PendingOrderFormDialog } from '../PendingOrderFormDialog'
import type { PendingOrder } from '../../lib/api/cockpitPendingOrdersApi'

// ── mock data ─────────────────────────────────────────────────────────────────

const mockOrder: PendingOrder = {
  id: 1,
  ticker: 'NVDA',
  setupType: 'BREAKOUT',
  entryPrice: 900.0,
  stopPrice: 860.0,
  shares: 20,
  target2r: 980.0,
  target3r: null,
  expirationDate: null,
  status: 'ACTIVE',
  lastClose: 870.0,
  distanceToTriggerPct: 3.45,
  riskPct: 1.5,
  notes: null,
  createdAt: '2026-04-20T10:00:00Z',
  updatedAt: '2026-04-20T10:00:00Z',
}

function makeOkResponse(data: unknown, status = 200) {
  return Promise.resolve({ ok: true, status, json: () => Promise.resolve({ data, message: 'success' }) })
}

function makeWrapper(qc?: QueryClient) {
  const client = qc ?? new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
  return { client, invalidateSpy }
}

function renderNewDialog(qc?: QueryClient) {
  const { client, invalidateSpy } = makeWrapper(qc)
  const onSaved = vi.fn()
  const onClose = vi.fn()
  render(
    <QueryClientProvider client={client}>
      <PendingOrderFormDialog mode="new" open onSaved={onSaved} onClose={onClose} />
    </QueryClientProvider>,
  )
  return { client, invalidateSpy, onSaved, onClose }
}

function renderEditDialog(order = mockOrder, qc?: QueryClient) {
  const { client, invalidateSpy } = makeWrapper(qc)
  const onSaved = vi.fn()
  const onClose = vi.fn()
  render(
    <QueryClientProvider client={client}>
      <PendingOrderFormDialog mode="edit" open onSaved={onSaved} onClose={onClose} initialOrder={order} />
    </QueryClientProvider>,
  )
  return { client, invalidateSpy, onSaved, onClose }
}

// ── setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => { vi.stubGlobal('fetch', vi.fn()) })
afterEach(() => vi.unstubAllGlobals())

// ── S15 validation failures ───────────────────────────────────────────────────

describe('S15 – validation failures', () => {
  it('ticker empty → error, no POST', async () => {
    renderNewDialog()
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '900' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '860' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '20' } })
    await userEvent.setup().click(screen.getByText('Add Order'))
    await waitFor(() => expect(screen.getByText('Ticker required')).toBeInTheDocument())
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter((c) => c[1]?.method === 'POST')).toHaveLength(0)
  })

  it('setupType not selected → error, no POST', async () => {
    renderNewDialog()
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '900' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '860' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '20' } })
    await userEvent.setup().click(screen.getByText('Add Order'))
    await waitFor(() => expect(screen.getByText('Setup type required')).toBeInTheDocument())
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter((c) => c[1]?.method === 'POST')).toHaveLength(0)
  })

  it('entryPrice ≤ 0 → error, no POST', async () => {
    renderNewDialog()
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '0' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '860' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '20' } })
    await userEvent.setup().click(screen.getByText('Add Order'))
    await waitFor(() => expect(screen.getAllByText('Must be > 0').length).toBeGreaterThan(0))
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter((c) => c[1]?.method === 'POST')).toHaveLength(0)
  })

  it('stopPrice ≤ 0 → error, no POST', async () => {
    renderNewDialog()
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '900' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '0' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '20' } })
    await userEvent.setup().click(screen.getByText('Add Order'))
    await waitFor(() => expect(screen.getAllByText('Must be > 0').length).toBeGreaterThan(0))
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter((c) => c[1]?.method === 'POST')).toHaveLength(0)
  })

  it('entryPrice ≤ stopPrice → error, no POST', async () => {
    renderNewDialog()
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '860' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '860' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '20' } })
    await userEvent.setup().click(screen.getByText('Add Order'))
    await waitFor(() => expect(screen.getByText('Entry must be > stop')).toBeInTheDocument())
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter((c) => c[1]?.method === 'POST')).toHaveLength(0)
  })

  it('shares ≤ 0 → error, no POST', async () => {
    renderNewDialog()
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '900' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '860' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '0' } })
    await userEvent.setup().click(screen.getByText('Add Order'))
    await waitFor(() => expect(screen.getAllByText('Must be > 0').length).toBeGreaterThan(0))
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter((c) => c[1]?.method === 'POST')).toHaveLength(0)
  })

  it('target2r ≤ entryPrice → error, no POST', async () => {
    renderNewDialog()
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '900' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '860' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Target 2R (optional)'), { target: { value: '850' } })
    await userEvent.setup().click(screen.getByText('Add Order'))
    await waitFor(() => expect(screen.getByText('Must be > entry price')).toBeInTheDocument())
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter((c) => c[1]?.method === 'POST')).toHaveLength(0)
  })

  it('expirationDate < today → error, no POST', async () => {
    renderNewDialog()
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'NVDA' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '900' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '860' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Expiration date (optional)'), { target: { value: '2020-01-01' } })
    await userEvent.setup().click(screen.getByText('Add Order'))
    await waitFor(() => expect(screen.getByText('Must be today or later')).toBeInTheDocument())
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter((c) => c[1]?.method === 'POST')).toHaveLength(0)
  })
})

// ── S16 new mode valid submit ─────────────────────────────────────────────────

describe('S16 – new mode valid submit → POST body camelCase + invalidate', () => {
  it('POST body has camelCase fields; success → invalidate cockpit-pending-orders + onSaved', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(mockOrder, 201)))
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    const onSaved = vi.fn()

    render(
      <QueryClientProvider client={qc}>
        <PendingOrderFormDialog mode="new" open onSaved={onSaved} onClose={vi.fn()} />
      </QueryClientProvider>,
    )

    const user = userEvent.setup()
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'nvda' } })
    fireEvent.change(screen.getByLabelText('Entry price'), { target: { value: '900' } })
    fireEvent.change(screen.getByLabelText('Stop price'), { target: { value: '860' } })
    fireEvent.change(screen.getByLabelText('Shares'), { target: { value: '20' } })
    // shadcn Select is mocked with native <select> so fireEvent.change works
    fireEvent.change(screen.getByTestId('native-select'), { target: { value: 'BREAKOUT' } })

    await user.click(screen.getByText('Add Order'))

    await waitFor(() => {
      const postCalls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
        (c) => c[1]?.method === 'POST',
      )
      expect(postCalls).toHaveLength(1)
      const body = JSON.parse(postCalls[0][1].body as string)
      expect(body.ticker).toBe('NVDA')
      expect(body.entryPrice).toBe(900)
      expect(body.stopPrice).toBe(860)
      expect(body.shares).toBe(20)
      expect(body.setupType).toBe('BREAKOUT')
      expect(body).not.toHaveProperty('entry_price')
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-pending-orders'] }),
      )
    })

    expect(onSaved).toHaveBeenCalled()
  })
})

// ── S17 edit mode dirty fields ────────────────────────────────────────────────

describe('S17 – edit mode: pre-fills initialOrder + PATCH only dirty fields', () => {
  it('pre-fills fields from initialOrder', () => {
    renderEditDialog()
    const stopInput = screen.getByLabelText('Stop price') as HTMLInputElement
    const entryInput = screen.getByLabelText('Entry price') as HTMLInputElement
    const sharesInput = screen.getByLabelText('Shares') as HTMLInputElement
    expect(stopInput.value).toBe('860')
    expect(entryInput.value).toBe('900')
    expect(sharesInput.value).toBe('20')
  })

  it('only changed field (stopPrice) sent in PATCH body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(mockOrder)))
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    const onSaved = vi.fn()

    render(
      <QueryClientProvider client={qc}>
        <PendingOrderFormDialog mode="edit" open onSaved={onSaved} onClose={vi.fn()} initialOrder={mockOrder} />
      </QueryClientProvider>,
    )

    const user = userEvent.setup({ pointerEventsCheck: 0 })
    const stopInput = screen.getByLabelText('Stop price')
    await user.clear(stopInput)
    await user.type(stopInput, '870')

    await user.click(screen.getByText('Save'))

    await waitFor(() => {
      const patchCalls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
        (c) => c[1]?.method === 'PATCH',
      )
      expect(patchCalls).toHaveLength(1)
      expect(patchCalls[0][0]).toContain('/cockpit/pending-orders/1')
      const body = JSON.parse(patchCalls[0][1].body as string)
      expect(body.stopPrice).toBe(870)
      // No other fields should be present
      expect(body).not.toHaveProperty('ticker')
      expect(body).not.toHaveProperty('entryPrice')
      expect(body).not.toHaveProperty('shares')
      expect(body).not.toHaveProperty('setupType')
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-pending-orders'] }),
      )
    })

    expect(onSaved).toHaveBeenCalled()
  })
})
