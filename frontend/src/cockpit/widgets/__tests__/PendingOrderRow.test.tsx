import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { PendingOrderRow } from '../_pendingOrderRow'
import type { PendingOrder } from '../../lib/api/cockpitPendingOrdersApi'

// ── mock sonner ───────────────────────────────────────────────────────────────

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
    expirationDate: null,
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
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ data, message: 'success' }) })
}

function renderRow(order: PendingOrder, onEdit = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
  render(
    <QueryClientProvider client={client}>
      <table><tbody>
        <PendingOrderRow order={order} onEdit={onEdit} />
      </tbody></table>
    </QueryClientProvider>,
  )
  return { client, invalidateSpy }
}

beforeEach(() => vi.stubGlobal('fetch', vi.fn()))
afterEach(() => vi.unstubAllGlobals())

// ── S6 distance 颜色 3 档 ──────────────────────────────────────────────────────

describe('S6 – distance color tiers', () => {
  it('|dist| > 5 → muted color style', () => {
    renderRow(makeOrder({ id: 1, distanceToTriggerPct: 8 }))
    const cell = screen.getByTestId('dist-cell-1')
    expect(cell.style.color).toBe('var(--color-text-muted)')
    expect(cell.className).not.toContain('font-bold')
  })

  it('|dist| = 3 (1–5 range) → no special style', () => {
    renderRow(makeOrder({ id: 1, distanceToTriggerPct: 3 }))
    const cell = screen.getByTestId('dist-cell-1')
    expect(cell.style.color).toBe('')
    expect(cell.className).not.toContain('font-bold')
  })

  it('|dist| = 0.5 (< 1) → font-bold className', () => {
    renderRow(makeOrder({ id: 1, distanceToTriggerPct: 0.5 }))
    const cell = screen.getByTestId('dist-cell-1')
    expect(cell.className).toContain('font-bold')
  })

  it('negative dist -7 → absolute value → muted color', () => {
    renderRow(makeOrder({ id: 1, distanceToTriggerPct: -7 }))
    const cell = screen.getByTestId('dist-cell-1')
    expect(cell.style.color).toBe('var(--color-text-muted)')
  })

  it('negative dist -0.4 → absolute value → font-bold', () => {
    renderRow(makeOrder({ id: 1, distanceToTriggerPct: -0.4 }))
    const cell = screen.getByTestId('dist-cell-1')
    expect(cell.className).toContain('font-bold')
  })

  it('dist null → "—" displayed', () => {
    renderRow(makeOrder({ id: 1, distanceToTriggerPct: null }))
    const cell = screen.getByTestId('dist-cell-1')
    expect(cell.textContent).toBe('—')
  })

  it('distance text format: +3.45%', () => {
    renderRow(makeOrder({ id: 1, distanceToTriggerPct: 3.45 }))
    expect(screen.getByTestId('dist-cell-1').textContent).toBe('+3.45%')
  })

  it('distance text format: -2.10%', () => {
    renderRow(makeOrder({ id: 1, distanceToTriggerPct: -2.1 }))
    expect(screen.getByTestId('dist-cell-1').textContent).toBe('-2.10%')
  })
})

// ── S8 button visibility ──────────────────────────────────────────────────────

describe('S8 – button visibility by status', () => {
  it('ACTIVE row shows [Triggered] and [Cancel]', () => {
    renderRow(makeOrder({ id: 1, status: 'ACTIVE' }))
    expect(screen.getByTestId('triggered-btn-1')).toBeInTheDocument()
    expect(screen.getByTestId('cancel-btn-1')).toBeInTheDocument()
  })

  it('ACTIVE row shows [Edit] and [✕]', () => {
    renderRow(makeOrder({ id: 1, status: 'ACTIVE' }))
    expect(screen.getByTestId('edit-btn-1')).toBeInTheDocument()
    expect(screen.getByTestId('delete-btn-1')).toBeInTheDocument()
  })

  it('TRIGGERED row does NOT show [Triggered] or [Cancel]', () => {
    renderRow(makeOrder({ id: 1, status: 'TRIGGERED' }))
    expect(screen.queryByTestId('triggered-btn-1')).not.toBeInTheDocument()
    expect(screen.queryByTestId('cancel-btn-1')).not.toBeInTheDocument()
  })

  it('TRIGGERED row still shows [Edit] and [✕]', () => {
    renderRow(makeOrder({ id: 1, status: 'TRIGGERED' }))
    expect(screen.getByTestId('edit-btn-1')).toBeInTheDocument()
    expect(screen.getByTestId('delete-btn-1')).toBeInTheDocument()
  })

  it('CANCELLED row does NOT show [Triggered] or [Cancel]', () => {
    renderRow(makeOrder({ id: 1, status: 'CANCELLED' }))
    expect(screen.queryByTestId('triggered-btn-1')).not.toBeInTheDocument()
    expect(screen.queryByTestId('cancel-btn-1')).not.toBeInTheDocument()
  })

  it('EXPIRED row does NOT show [Triggered] or [Cancel]', () => {
    renderRow(makeOrder({ id: 1, status: 'EXPIRED' }))
    expect(screen.queryByTestId('triggered-btn-1')).not.toBeInTheDocument()
    expect(screen.queryByTestId('cancel-btn-1')).not.toBeInTheDocument()
  })
})

// ── S10 Cancel direct PATCH ───────────────────────────────────────────────────

describe('S10 – Cancel button → direct PATCH no dialog', () => {
  it('click Cancel → PATCH status=CANCELLED immediately', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse({ ...makeOrder(), status: 'CANCELLED' })))
    const { invalidateSpy } = renderRow(makeOrder({ id: 1, status: 'ACTIVE' }))
    fireEvent.click(screen.getByTestId('cancel-btn-1'))
    await waitFor(() => {
      const patchCalls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
        (c) => c[1]?.method === 'PATCH',
      )
      expect(patchCalls).toHaveLength(1)
      const body = JSON.parse(patchCalls[0][1].body as string)
      expect(body.status).toBe('CANCELLED')
    })
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-pending-orders'] }),
      )
    })
  })
})

// ── S11 Edit opens dialog ─────────────────────────────────────────────────────

describe('S11 – Edit button → calls onEdit with order', () => {
  it('click Edit → onEdit callback called with the order', () => {
    const onEdit = vi.fn()
    const order = makeOrder({ id: 1, status: 'ACTIVE' })
    renderRow(order, onEdit)
    fireEvent.click(screen.getByTestId('edit-btn-1'))
    expect(onEdit).toHaveBeenCalledWith(order)
  })
})

// ── expirationDate null → "—" ─────────────────────────────────────────────────

describe('expirationDate null → "—"', () => {
  it('null expirationDate displays "—"', () => {
    renderRow(makeOrder({ id: 1, expirationDate: null }))
    // expiration is the 8th column
    const cells = screen.getAllByRole('cell')
    const expCell = cells[7]  // Ticker, Setup, Entry, Stop, Last, Dist, Risk%, Exp
    expect(expCell.textContent).toBe('—')
  })
})
