// Mock shadcn Select with native <select> so JSDOM form interactions work.
vi.mock('@/components/ui/select', () => ({
  Select: ({
    value,
    onValueChange,
    children,
  }: {
    value: string
    onValueChange: (v: string) => void
    children: React.ReactNode
  }) => (
    <select
      data-testid="filter-select"
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
    >
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectValue: () => null,
  SelectContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectItem: ({ value, children }: { value: string; children: React.ReactNode }) => (
    <option value={value}>{children}</option>
  ),
}))

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { RepricingTriggerWidget } from '../RepricingTriggerWidget'
import { useCockpitStore } from '@/store/cockpitStore'

// ── Fixtures ─────────────────────────────────────────────────────────────────

const earningsAccelTrigger = {
  ticker: 'AAPL',
  triggerType: 'EARNINGS_ACCEL',
  detectedDate: '2026-05-13',
  confidence: 0.80,
  evidence: { epsYoyGrowth: [78], revenueYoyGrowth: [32], quarters: ['Q1-2026'] },
  computedAt: '2026-05-20T22:40:00Z',
}

const marginExpTrigger = {
  ticker: 'NVDA',
  triggerType: 'MARGIN_EXPANSION',
  detectedDate: '2026-05-15',
  confidence: 0.80,
  evidence: {
    grossMarginTrend: [0.40, 0.49],
    fcfMarginTrend: [0.10, 0.15],
    quarters: ['Q4-2025', 'Q1-2026'],
    triggerMetric: 'gross_margin',
    expansionBp: 900,
  },
  computedAt: '2026-05-20T22:40:00Z',
}

const balanceInflectTrigger = {
  ticker: 'TSLA',
  triggerType: 'BALANCE_INFLECTION',
  detectedDate: '2026-05-14',
  confidence: 0.50,
  evidence: {
    netDebtTrend: [100, 79],
    fcfTrend: [10, 15],
    quarters: ['Q4-2025', 'Q1-2026'],
    triggerMetric: 'net_debt',
  },
  computedAt: '2026-05-20T22:40:00Z',
}

const THREE_TRIGGERS_PAYLOAD = {
  triggers: [earningsAccelTrigger, marginExpTrigger, balanceInflectTrigger],
  totalCount: 3,
  computedAt: '2026-05-20T22:40:00Z',
}

const EMPTY_PAYLOAD = {
  triggers: [],
  totalCount: 0,
  computedAt: '2026-05-20T22:40:00Z',
}

// ── Helpers ───────────────────────────────────────────────────────────────────

type MockResponse = { ok: boolean; status: number; json: () => Promise<unknown> }

function makeOkResponse(data: unknown): MockResponse {
  return { ok: true, status: 200, json: () => Promise.resolve({ data, message: 'success' }) }
}

function makeErrResponse(status: number): MockResponse {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({ error: { code: 'ERR', message: 'error' } }),
  }
}

function renderWidget() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <RepricingTriggerWidget />
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

// ── Tests B1–B9 ───────────────────────────────────────────────────────────────

describe('B1 – mount triggers initial fetch, shows loading skeleton', () => {
  it('calls getAllActiveTriggers once on mount and shows Loading...', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeOkResponse(THREE_TRIGGERS_PAYLOAD))
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    expect(screen.getByText(/Loading/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1)
      const [url] = fetchMock.mock.calls[0]
      expect(url).toContain('/cockpit/repricing-triggers')
    })
  })
})

describe('B2 – 3 rows render with correct column content', () => {
  it('renders 3 table rows with ticker / trigger chip / date / conf / evidence columns', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(THREE_TRIGGERS_PAYLOAD)))
    renderWidget()
    await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument())

    // All 3 tickers present
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('NVDA')).toBeInTheDocument()
    expect(screen.getByText('TSLA')).toBeInTheDocument()

    // Trigger chip short labels (also appear in select options, so use getAllByText)
    expect(screen.getAllByText('EarningsAccel').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('MarginExp').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('BalanceInflect').length).toBeGreaterThanOrEqual(1)
    // Confirm chip spans are rendered with data-trigger-type attribute
    expect(document.querySelectorAll('[data-trigger-type]')).toHaveLength(3)

    // Dates
    expect(screen.getByText('2026-05-13')).toBeInTheDocument()
    expect(screen.getByText('2026-05-15')).toBeInTheDocument()
    expect(screen.getByText('2026-05-14')).toBeInTheDocument()

    // Confidence values
    expect(screen.getAllByText('0.80').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('0.50')).toBeInTheDocument()

    // Table headers in correct order
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    expect(headers).toEqual(['Ticker', 'Trigger', 'Date', 'Conf', 'Evidence'])
  })
})

describe('B3 – filter switch → query refetches with triggerType param', () => {
  it('URL contains triggerType=MARGIN_EXPANSION after filter change', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeOkResponse(THREE_TRIGGERS_PAYLOAD))
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument())

    // Change filter to MARGIN_EXPANSION via native select
    const select = screen.getByTestId('filter-select')
    fireEvent.change(select, { target: { value: 'MARGIN_EXPANSION' } })

    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([url]) => url as string)
      const filtered = calls.find((u) => u.includes('triggerType=MARGIN_EXPANSION'))
      expect(filtered).toBeDefined()
    })
  })
})

describe('B4 – row click → cockpitStore.setSelectedTicker called', () => {
  it('clicking NVDA row sets selectedTicker to "NVDA"', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(THREE_TRIGGERS_PAYLOAD)))
    renderWidget()
    await waitFor(() => expect(screen.getByText('NVDA')).toBeInTheDocument())

    fireEvent.click(screen.getByText('NVDA'))
    expect(useCockpitStore.getState().selectedTicker).toBe('NVDA')
  })
})

describe('B5 – empty state: totalCount=0', () => {
  it('renders EmptyState text when no active triggers', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(EMPTY_PAYLOAD)))
    renderWidget()
    await waitFor(() =>
      expect(screen.getByText(/今日全市场无 active trigger/)).toBeInTheDocument(),
    )
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})

describe('B6 – error state: shows error message + retry button', () => {
  it('renders 加载失败 and 重试 button on network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeErrResponse(500)))
    renderWidget()
    await waitFor(() => expect(screen.getByText(/加载失败，请稍后重试/)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /重试/ })).toBeInTheDocument()
  })
})

describe('B7 – refresh button click triggers refetch', () => {
  it('clicking refresh button fires a new fetch request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeOkResponse(THREE_TRIGGERS_PAYLOAD))
    vi.stubGlobal('fetch', fetchMock)
    renderWidget()
    await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument())
    const initialCount = fetchMock.mock.calls.length

    fireEvent.click(screen.getByRole('button', { name: /Refresh repricing triggers/i }))

    await waitFor(() => {
      expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCount)
    })
  })
})

describe('B8 – 5 trigger types have correct color CSS variables in inline style', () => {
  it('each trigger chip has var(--color-trigger-*) in its inline color style', async () => {
    const allTypesTriggers = [
      {
        ticker: 'T1',
        triggerType: 'EARNINGS_ACCEL',
        detectedDate: '2026-05-15',
        confidence: 0.8,
        evidence: { epsYoyGrowth: [50], revenueYoyGrowth: [20], quarters: ['Q1'] },
        computedAt: '2026-05-20T22:40:00Z',
      },
      {
        ticker: 'T2',
        triggerType: 'MARGIN_EXPANSION',
        detectedDate: '2026-05-15',
        confidence: 0.7,
        evidence: {
          grossMarginTrend: [0.3, 0.4],
          fcfMarginTrend: [0.1, 0.15],
          quarters: ['Q1'],
          triggerMetric: 'gross_margin',
          expansionBp: 500,
        },
        computedAt: '2026-05-20T22:40:00Z',
      },
      {
        ticker: 'T3',
        triggerType: 'NEW_PRODUCT',
        detectedDate: '2026-05-15',
        confidence: 0.6,
        evidence: {
          keywordHits: { iphone: 3 },
          newsLinks: [{ title: 'n', url: 'u', publishedAt: '2026' }],
        },
        computedAt: '2026-05-20T22:40:00Z',
      },
      {
        ticker: 'T4',
        triggerType: 'SECTOR_CYCLE',
        detectedDate: '2026-05-15',
        confidence: 0.65,
        evidence: { sector: 'XLK', rsHistory: [35, 68], priceVs200d: 1.05 },
        computedAt: '2026-05-20T22:40:00Z',
      },
      {
        ticker: 'T5',
        triggerType: 'BALANCE_INFLECTION',
        detectedDate: '2026-05-15',
        confidence: 0.55,
        evidence: {
          netDebtTrend: [100, 79],
          fcfTrend: [10, 15],
          quarters: ['Q1'],
          triggerMetric: 'net_debt',
        },
        computedAt: '2026-05-20T22:40:00Z',
      },
    ]
    const payload = { triggers: allTypesTriggers, totalCount: 5, computedAt: '2026-05-20T22:40:00Z' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(payload)))
    renderWidget()
    await waitFor(() => expect(screen.getByText('T1')).toBeInTheDocument())

    const chips = document.querySelectorAll('[data-trigger-type]')
    expect(chips).toHaveLength(5)

    const colorVarMap: Record<string, string> = {
      EARNINGS_ACCEL: 'var(--color-trigger-earnings-accel)',
      MARGIN_EXPANSION: 'var(--color-trigger-margin-expansion)',
      NEW_PRODUCT: 'var(--color-trigger-new-product)',
      SECTOR_CYCLE: 'var(--color-trigger-sector-cycle)',
      BALANCE_INFLECTION: 'var(--color-trigger-balance-inflection)',
    }
    chips.forEach((chip) => {
      const type = chip.getAttribute('data-trigger-type')!
      const style = (chip as HTMLElement).style.color
      expect(style).toBe(colorVarMap[type])
    })
  })
})

describe('B9 – evidence summary renders correctly for all 5 trigger types', () => {
  it('EARNINGS_ACCEL → "eps yoy 78%"', async () => {
    const payload = {
      triggers: [earningsAccelTrigger],
      totalCount: 1,
      computedAt: '2026-05-20T22:40:00Z',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(payload)))
    renderWidget()
    await waitFor(() => expect(screen.getByText('eps yoy 78%')).toBeInTheDocument())
  })

  it('MARGIN_EXPANSION → "gross_margin +900bp"', async () => {
    const payload = {
      triggers: [marginExpTrigger],
      totalCount: 1,
      computedAt: '2026-05-20T22:40:00Z',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(payload)))
    renderWidget()
    await waitFor(() => expect(screen.getByText('gross_margin +900bp')).toBeInTheDocument())
  })

  it('NEW_PRODUCT → "1 keywords / 1 news"', async () => {
    const trigger = {
      ticker: 'AAPL',
      triggerType: 'NEW_PRODUCT',
      detectedDate: '2026-05-15',
      confidence: 0.6,
      evidence: {
        keywordHits: { iphone: 3 },
        newsLinks: [{ title: 'n', url: 'u', publishedAt: '2026' }],
      },
      computedAt: '2026-05-20T22:40:00Z',
    }
    const payload = { triggers: [trigger], totalCount: 1, computedAt: '2026-05-20T22:40:00Z' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(payload)))
    renderWidget()
    await waitFor(() => expect(screen.getByText('1 keywords / 1 news')).toBeInTheDocument())
  })

  it('SECTOR_CYCLE → "XLK RS 35→68"', async () => {
    const trigger = {
      ticker: 'XLK',
      triggerType: 'SECTOR_CYCLE',
      detectedDate: '2026-05-15',
      confidence: 0.65,
      evidence: { sector: 'XLK', rsHistory: [35, 68], priceVs200d: 1.05 },
      computedAt: '2026-05-20T22:40:00Z',
    }
    const payload = { triggers: [trigger], totalCount: 1, computedAt: '2026-05-20T22:40:00Z' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(payload)))
    renderWidget()
    await waitFor(() => expect(screen.getByText('XLK RS 35→68')).toBeInTheDocument())
  })

  it('BALANCE_INFLECTION net_debt → "net_debt ↓ 21%"', async () => {
    const trigger = {
      ticker: 'TSLA',
      triggerType: 'BALANCE_INFLECTION',
      detectedDate: '2026-05-14',
      confidence: 0.5,
      evidence: {
        netDebtTrend: [100, 79],
        fcfTrend: [10, 15],
        quarters: ['Q4-2025', 'Q1-2026'],
        triggerMetric: 'net_debt',
      },
      computedAt: '2026-05-20T22:40:00Z',
    }
    const payload = { triggers: [trigger], totalCount: 1, computedAt: '2026-05-20T22:40:00Z' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeOkResponse(payload)))
    renderWidget()
    await waitFor(() => expect(screen.getByText('net_debt ↓ 21%')).toBeInTheDocument())
  })
})
