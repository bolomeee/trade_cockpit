import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ActionListWidget } from '../ActionListWidget'
import type { ActionItem, TodayActionsPayload } from '../../lib/api/cockpitActionsApi'

// ── Store mock ────────────────────────────────────────────────────────────────

const mockSetSelectedTicker = vi.fn()
vi.mock('@/store/cockpitStore', () => ({
  useCockpitStore: (
    selector: (s: { selectedTicker: null; setSelectedTicker: typeof mockSetSelectedTicker }) => unknown,
  ) => selector({ selectedTicker: null, setSelectedTicker: mockSetSelectedTicker }),
}))

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeAction(overrides: Partial<ActionItem> = {}): ActionItem {
  return {
    ticker: 'AAPL',
    actionType: 'raise_stop',
    rationale: 'Stop is well below breakeven, raise to protect gains.',
    refs: { positionId: 1, rMultiple: 2.1 },
    ...overrides,
  }
}

function makeOkResponse(payload: TodayActionsPayload) {
  return { ok: true, json: () => Promise.resolve({ data: payload, message: 'success' }) }
}

function makeFetch(payload: TodayActionsPayload | null, statusCode = 200) {
  if (statusCode !== 200 || payload === null) {
    return vi.fn().mockResolvedValue({
      ok: false,
      status: statusCode,
      json: () => Promise.resolve({ error: { code: 'SERVER_ERROR', message: 'fail' } }),
    }) as unknown as typeof fetch
  }
  return vi.fn().mockResolvedValue(makeOkResponse(payload)) as unknown as typeof fetch
}

function renderWidget(fetchFn?: typeof fetch) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  if (fetchFn) vi.stubGlobal('fetch', fetchFn)
  render(
    <QueryClientProvider client={qc}>
      <ActionListWidget />
    </QueryClientProvider>,
  )
  return { qc }
}

const emptyPayload: TodayActionsPayload = {
  asOfDate: '2026-04-24',
  mustAct: [],
  monitor: [],
  noAction: [],
}

beforeEach(() => {
  vi.stubGlobal('fetch', makeFetch(emptyPayload))
  mockSetSelectedTicker.mockClear()
})
afterEach(() => vi.unstubAllGlobals())

// ── W1: loading state ─────────────────────────────────────────────────────────

describe('W1 – loading state', () => {
  it('shows 3 skeletons; no asOfDate in header', () => {
    // Use a never-resolving fetch to stay in loading state
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))
    renderWidget()
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]')
    expect(skeletons.length).toBe(3)
    expect(screen.queryByTestId('action-as-of-date')).not.toBeInTheDocument()
  })
})

// ── W2: success all-empty ─────────────────────────────────────────────────────

describe('W2 – success all-empty (three sections 0)', () => {
  it('shows empty-state "暂无今日动作"; no section rendered', async () => {
    renderWidget(makeFetch(emptyPayload))
    await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument())
    expect(screen.getByText('暂无今日动作')).toBeInTheDocument()
    expect(screen.queryByTestId('action-section-must')).not.toBeInTheDocument()
    expect(screen.queryByTestId('action-section-monitor')).not.toBeInTheDocument()
    expect(screen.queryByTestId('action-section-noaction')).not.toBeInTheDocument()
  })
})

// ── W3: error state ───────────────────────────────────────────────────────────

describe('W3 – error state', () => {
  it('shows error-banner "加载失败，请稍后重试"', async () => {
    renderWidget(makeFetch(null, 500))
    await waitFor(() => expect(screen.getByTestId('error-banner')).toBeInTheDocument())
    expect(screen.getByText('加载失败，请稍后重试')).toBeInTheDocument()
  })
})

// ── W4: success with 1 mustAct raise_stop ────────────────────────────────────

describe('W4 – success with 1 mustAct raise_stop', () => {
  it('renders must section; shows ticker + label + rationale; no monitor/noaction section', async () => {
    const payload: TodayActionsPayload = {
      asOfDate: '2026-04-24',
      mustAct: [makeAction({ ticker: 'AAPL', actionType: 'raise_stop', rationale: 'Stop too loose.' })],
      monitor: [],
      noAction: [],
    }
    renderWidget(makeFetch(payload))
    await waitFor(() => expect(screen.getByTestId('action-section-must')).toBeInTheDocument())
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('Raise Stop')).toBeInTheDocument()
    expect(screen.getByText('Stop too loose.')).toBeInTheDocument()
    expect(screen.queryByTestId('action-section-monitor')).not.toBeInTheDocument()
    expect(screen.queryByTestId('action-section-noaction')).not.toBeInTheDocument()
  })
})

// ── W5: success monitor + noAction, mustAct empty ────────────────────────────

describe('W5 – success monitor + noAction, no mustAct section', () => {
  it('renders monitor and noaction sections; must section absent', async () => {
    const payload: TodayActionsPayload = {
      asOfDate: '2026-04-24',
      mustAct: [],
      monitor: [makeAction({ ticker: 'TSLA', actionType: 'approaching_trigger' })],
      noAction: [makeAction({ ticker: 'NVDA', actionType: 'stable_position' })],
    }
    renderWidget(makeFetch(payload))
    await waitFor(() => expect(screen.getByTestId('action-section-monitor')).toBeInTheDocument())
    expect(screen.getByTestId('action-section-noaction')).toBeInTheDocument()
    expect(screen.queryByTestId('action-section-must')).not.toBeInTheDocument()
  })
})

// ── W6: all three sections, must → monitor → noaction DOM order ──────────────

describe('W6 – three sections present in must → monitor → noaction order', () => {
  it('DOM order is must, monitor, noaction', async () => {
    const payload: TodayActionsPayload = {
      asOfDate: '2026-04-24',
      mustAct: [makeAction({ ticker: 'AAPL', actionType: 'raise_stop' })],
      monitor: [makeAction({ ticker: 'TSLA', actionType: 'approaching_trigger' })],
      noAction: [makeAction({ ticker: 'NVDA', actionType: 'stable_position' })],
    }
    renderWidget(makeFetch(payload))
    await waitFor(() => expect(screen.getByTestId('action-section-must')).toBeInTheDocument())
    const sections = document.querySelectorAll('[data-testid^="action-section-"]')
    expect(sections).toHaveLength(3)
    expect(sections[0].getAttribute('data-testid')).toBe('action-section-must')
    expect(sections[1].getAttribute('data-testid')).toBe('action-section-monitor')
    expect(sections[2].getAttribute('data-testid')).toBe('action-section-noaction')
  })
})

// ── W7: section title includes count ─────────────────────────────────────────

describe('W7 – section title includes (N) count', () => {
  it('must section title shows "Must Act (1)"', async () => {
    const payload: TodayActionsPayload = {
      asOfDate: '2026-04-24',
      mustAct: [makeAction({ ticker: 'AAPL', actionType: 'raise_stop' })],
      monitor: [],
      noAction: [],
    }
    renderWidget(makeFetch(payload))
    await waitFor(() => expect(screen.getByText('Must Act (1)')).toBeInTheDocument())
  })
})

// ── W8: row click → setSelectedTicker called ─────────────────────────────────

describe('W8 – row click triggers setSelectedTicker', () => {
  it('clicking the row calls setSelectedTicker with the ticker', async () => {
    const payload: TodayActionsPayload = {
      asOfDate: '2026-04-24',
      mustAct: [makeAction({ ticker: 'AAPL', actionType: 'raise_stop' })],
      monitor: [],
      noAction: [],
    }
    renderWidget(makeFetch(payload))
    await waitFor(() => expect(screen.getByTestId('action-row-must-AAPL')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('action-row-must-AAPL'))
    expect(mockSetSelectedTicker).toHaveBeenCalledWith('AAPL')
  })
})

// ── W9: hover tooltip contains rationale + refs JSON ─────────────────────────

describe('W9 – hover title attribute contains rationale and refs JSON', () => {
  it('row title includes rationale text and refs JSON substring', async () => {
    const payload: TodayActionsPayload = {
      asOfDate: '2026-04-24',
      mustAct: [
        makeAction({
          ticker: 'AAPL',
          actionType: 'raise_stop',
          rationale: 'R-multiple exceeded 2x, raise stop.',
          refs: { positionId: 99 },
        }),
      ],
      monitor: [],
      noAction: [],
    }
    renderWidget(makeFetch(payload))
    await waitFor(() => expect(screen.getByTestId('action-row-must-AAPL')).toBeInTheDocument())
    const row = screen.getByTestId('action-row-must-AAPL')
    expect(row.getAttribute('title')).toContain('R-multiple exceeded 2x, raise stop.')
    expect(row.getAttribute('title')).toContain('"positionId"')
  })
})

// ── W10: header asOfDate shows ISO string ────────────────────────────────────

describe('W10 – header right asOfDate shows ISO string', () => {
  it('asOfDate testid shows the ISO date from payload', async () => {
    const payload: TodayActionsPayload = {
      asOfDate: '2026-04-24',
      mustAct: [makeAction()],
      monitor: [],
      noAction: [],
    }
    renderWidget(makeFetch(payload))
    await waitFor(() => expect(screen.getByTestId('action-as-of-date')).toBeInTheDocument())
    expect(screen.getByTestId('action-as-of-date').textContent).toBe('2026-04-24')
  })
})

// ── Action label mapping coverage (all 6 actionType values) ──────────────────

describe('Action label mapping – all 6 actionType values', () => {
  const cases: Array<[string, string]> = [
    ['raise_stop', 'Raise Stop'],
    ['cancel_order', 'Cancel Order'],
    ['reduce_before_earnings', 'Reduce (Earnings)'],
    ['tighten_stop', 'Tighten Stop'],
    ['approaching_trigger', 'Approaching Trigger'],
    ['stable_position', 'Stable'],
  ]

  it.each(cases)('actionType=%s → label "%s"', async (actionType, label) => {
    const payload: TodayActionsPayload = {
      asOfDate: '2026-04-24',
      mustAct: [makeAction({ actionType: actionType as ActionItem['actionType'] })],
      monitor: [],
      noAction: [],
    }
    renderWidget(makeFetch(payload))
    await waitFor(() => expect(screen.getByText(label)).toBeInTheDocument())
    vi.unstubAllGlobals()
  })
})
