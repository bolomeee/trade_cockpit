import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { TooltipProvider } from '@/components/ui/tooltip'
import { DecisionPanelWidget } from '../DecisionPanelWidget'
import { useCockpitStore } from '@/store/cockpitStore'
import type { SetupItem, SetupMonitorData } from '../../lib/api/setupMonitorApi'
import type { CockpitRegimeData } from '../../lib/api/cockpitRegimeApi'

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
    <TooltipProvider>
      <QueryClientProvider client={qc}>
        <DecisionPanelWidget />
      </QueryClientProvider>
    </TooltipProvider>,
  )
}

function renderWidgetWith(qc: QueryClient) {
  return render(
    <TooltipProvider>
      <QueryClientProvider client={qc}>
        <DecisionPanelWidget />
      </QueryClientProvider>
    </TooltipProvider>,
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
    renderWidgetWith(qc)

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

// ── §T — AI Trade Plan ────────────────────────────────────────────────────────

const mockAiSuccess = {
  memoId: 1,
  taskType: 'trade_plan',
  schemaVersion: '1.0',
  output: {
    memo: 'Buy NVDA at the breakout of 850. Risk is well-defined.',
    management: ['Trail stop below 5d MA', 'Reduce at 2R', 'Exit fully at 3R'],
    entry: 850,
    stop: 820,
    size: 33,
  },
  meta: {
    modelUsed: 'claude-sonnet-4-6',
    tier: 'critical',
    tokensIn: 120,
    tokensOut: 200,
    costUsd: 0.002,
    latencyMs: 800,
    cacheHit: false,
  },
}

function makeRoutedFetch(opts: {
  decisionStatus?: 200 | 404 | 422
  aiStatus?: 200 | 409 | 502
  aiMeta?: Partial<typeof mockAiSuccess.meta>
  decisionSequence?: Array<Partial<typeof mockDecision>>
  onAiCall?: (body: { input: Record<string, unknown>; noCache: boolean }) => void
  pendingAi?: boolean
} = {}) {
  const {
    decisionStatus = 200,
    aiStatus = 200,
    aiMeta,
    decisionSequence,
    onAiCall,
    pendingAi = false,
  } = opts
  let decisionCallCount = 0

  return vi.fn((url: string, init?: RequestInit) => {
    const urlStr = url as string

    if (urlStr.includes('/cockpit/decision/')) {
      decisionCallCount++
      if (decisionStatus === 404) {
        return Promise.resolve({
          ok: false, status: 404,
          json: () => Promise.resolve({ error: { code: 'NOT_FOUND', message: 'not found' } }),
        })
      }
      if (decisionStatus === 422) {
        return Promise.resolve({
          ok: false, status: 422,
          json: () => Promise.resolve({ error: { code: 'VALIDATION_ERROR', message: 'entry must be > stop' } }),
        })
      }
      let responseData = mockDecision
      if (decisionSequence && decisionSequence.length > 0) {
        const idx = Math.min(decisionCallCount - 1, decisionSequence.length - 1)
        responseData = { ...mockDecision, ...decisionSequence[idx] }
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ data: responseData }) })
    }

    if (urlStr.includes('/ai/trade_plan')) {
      if (onAiCall && init?.body) {
        onAiCall(JSON.parse(init.body as string))
      }
      if (pendingAi) {
        return new Promise(() => {})
      }
      if (aiStatus === 409) {
        return Promise.resolve({
          ok: false, status: 409,
          json: () => Promise.resolve({ error: { code: 'AI_GUARDRAIL_VIOLATION', message: 'guardrail violation' } }),
        })
      }
      if (aiStatus === 502) {
        return Promise.resolve({
          ok: false, status: 502,
          json: () => Promise.resolve({ error: { code: 'AI_PROVIDER_ERROR', message: 'provider error' } }),
        })
      }
      const response = aiMeta
        ? { ...mockAiSuccess, meta: { ...mockAiSuccess.meta, ...aiMeta } }
        : mockAiSuccess
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ data: response }) })
    }

    return Promise.reject(new Error(`Unexpected URL: ${url}`))
  }) as unknown as typeof fetch
}

describe('T1 – decision loaded → AI button renders, no AI fetch', () => {
  it('shows [Generate AI Plan] button; /ai/trade_plan not called', async () => {
    vi.stubGlobal('fetch', makeDecisionFetch())
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument()
    })
    const aiCalls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      ([url]: [string]) => url.includes('/ai/trade_plan'),
    )
    expect(aiCalls.length).toBe(0)
  })
})

describe('T2 – empty state (no ticker) → no AI section', () => {
  it('AI trigger button does not exist when no ticker is selected', () => {
    vi.stubGlobal('fetch', vi.fn())
    renderWidget()
    expect(screen.queryByTestId('ai-plan-trigger')).not.toBeInTheDocument()
  })
})

describe('T3 – decision 404 / 422 / error → no AI section', () => {
  it('404: no AI trigger', async () => {
    vi.stubGlobal('fetch', makeDecisionFetch(404))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByText('无 setup 数据，可手动 override entry/stop')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('ai-plan-trigger')).not.toBeInTheDocument()
  })

  it('422: no AI trigger', async () => {
    vi.stubGlobal('fetch', makeDecisionFetch(422))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByText('entry 必须大于 stop')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('ai-plan-trigger')).not.toBeInTheDocument()
  })
})

describe('T4 – click button → POST body has 11 renamed fields', () => {
  it('body.input has entry/stop/size (renamed) + 8 direct fields', async () => {
    let capturedBody: { input: Record<string, unknown>; noCache: boolean } | null = null
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ onAiCall: (b) => { capturedBody = b } }),
    )
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))
    await waitFor(() => expect(capturedBody).not.toBeNull())

    const input = capturedBody!.input
    expect(input.ticker).toBe('NVDA')
    expect(input.setupType).toBe('BREAKOUT')
    expect(input.setupQuality).toBe('A')
    expect(input.entry).toBe(850)           // entryPrice → entry
    expect(input.stop).toBe(820)            // stopPrice → stop
    expect(input.target2r).toBe(910)
    expect(input.target3r).toBe(940)
    expect(input.size).toBe(33)             // suggestedShares → size
    expect(input.rewardRisk).toBe(2)
    expect(input.accountRiskPct).toBe(0.99)
    expect(input.earningsRisk).toBe('SAFE')
    expect(input.deterministicHash).toBe('abc123de456789')
  })
})

describe('T5 – POST body has no extra fields (schema extra: forbid)', () => {
  it('body.input excludes effectiveRiskPct / regimeCap / userSettingCap / earningsDate / riskPerShare / positionValue', async () => {
    let capturedInput: Record<string, unknown> | null = null
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({ onAiCall: (b) => { capturedInput = b.input } }),
    )
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))
    await waitFor(() => expect(capturedInput).not.toBeNull())

    const forbidden = [
      'effectiveRiskPct', 'regimeCap', 'userSettingCap',
      'earningsDate', 'riskPerShare', 'positionValue',
    ]
    for (const field of forbidden) {
      expect(capturedInput).not.toHaveProperty(field)
    }
    expect(Object.keys(capturedInput!).length).toBe(12)
  })
})

describe('T6 – loading state → 2 Skeletons', () => {
  it('shows ai-plan-skeletons while AI fetch is pending', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ pendingAi: true }))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-plan-skeletons')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ai-plan-skeleton-memo')).toBeInTheDocument()
    expect(screen.getByTestId('ai-plan-skeleton-mgmt')).toBeInTheDocument()
  })
})

describe('T7 – success → memo / management / guardrail badge / cache badge', () => {
  it('renders all success state elements with Generated cache badge', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch())
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-plan-result')).toBeInTheDocument()
    })

    expect(screen.getByTestId('ai-plan-memo').textContent).toBe(mockAiSuccess.output.memo)
    expect(screen.getByTestId('ai-plan-guardrail-passed').textContent).toContain('Guardrail passed')

    const items = screen.getAllByRole('listitem')
    expect(items.length).toBe(mockAiSuccess.output.management.length)
    expect(screen.getByTestId('ai-plan-management-item-0').textContent).toBe(mockAiSuccess.output.management[0])

    expect(screen.getByTestId('ai-plan-cache-badge').textContent).toContain('Generated')
    expect(screen.getByTestId('ai-plan-cache-badge').textContent).toContain(mockAiSuccess.meta.modelUsed)
  })
})

describe('T8 – meta.cacheHit=true → cache badge shows "Cached"', () => {
  it('renders "Cached" badge when cacheHit is true', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ aiMeta: { cacheHit: true } }))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-plan-cache-badge')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ai-plan-cache-badge').textContent).toBe('Cached')
  })
})

describe('T9 – 409 AI_GUARDRAIL_VIOLATION → red banner, DecisionCard unaffected', () => {
  it('shows red banner message; memo/management absent; DecisionCard fields still present', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ aiStatus: 409 }))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-plan-guardrail-error')).toBeInTheDocument()
    })

    const msg = screen.getByTestId('ai-plan-guardrail-message').textContent ?? ''
    expect(msg).toContain('AI 输出被拦截')
    expect(msg).toContain('数字不匹配')

    expect(screen.queryByTestId('ai-plan-memo')).not.toBeInTheDocument()
    expect(screen.queryByTestId('ai-plan-management-list')).not.toBeInTheDocument()

    // DecisionCard fields still present
    expect(screen.getByText('850.00')).toBeInTheDocument()
    expect(screen.getByText('820.00')).toBeInTheDocument()
  })
})

describe('T10 – 502 AI_PROVIDER_ERROR → "AI 暂不可用", DecisionCard/form unaffected', () => {
  it('shows generic error; override form inputs remain interactive', async () => {
    vi.stubGlobal('fetch', makeRoutedFetch({ aiStatus: 502 }))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-plan-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ai-plan-error').textContent).toContain('AI 暂不可用')

    // DecisionCard still renders
    expect(screen.getByText('850.00')).toBeInTheDocument()

    // Override form inputs still interactive
    const inputs = screen.getAllByPlaceholderText('—')
    expect(inputs.length).toBe(3)
    fireEvent.change(inputs[0], { target: { value: '855' } })
    expect((inputs[0] as HTMLInputElement).value).toBe('855')
  })
})

describe('T11 – close→reopen same hash → fetch count = 1 (cache hit)', () => {
  it('re-opening AI section with same deterministicHash does not fire a second request', async () => {
    const fetchMock = makeRoutedFetch()
    vi.stubGlobal('fetch', fetchMock)
    useCockpitStore.setState({ selectedTicker: 'NVDA' })

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    renderWidgetWith(qc)

    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())

    // Open AI section
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))
    await waitFor(() => expect(screen.getByTestId('ai-plan-result')).toBeInTheDocument())

    const aiCallsAfterFirst = (fetchMock.mock.calls as Array<[string]>).filter(
      ([url]) => url.includes('/ai/trade_plan'),
    ).length
    expect(aiCallsAfterFirst).toBe(1)

    // Close
    fireEvent.click(screen.getByTestId('ai-plan-close'))
    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())

    // Reopen — same queryKey → cache hit → no new fetch
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))
    await waitFor(() => expect(screen.getByTestId('ai-plan-result')).toBeInTheDocument())

    const aiCallsAfterReopen = (fetchMock.mock.calls as Array<[string]>).filter(
      ([url]) => url.includes('/ai/trade_plan'),
    ).length
    expect(aiCallsAfterReopen).toBe(1)
  })
})

describe('T12 – new decision hash (via Recompute) → AI auto-refetches', () => {
  it('AI fetch count increments and new call body has the new deterministicHash', async () => {
    const mockDecision2 = { ...mockDecision, deterministicHash: 'xyz789ab012345' }
    let decisionCallCount = 0

    const fetchMock = vi.fn((url: string) => {
      const urlStr = url as string
      if (urlStr.includes('/cockpit/decision/')) {
        decisionCallCount++
        const data = decisionCallCount >= 2 ? mockDecision2 : mockDecision
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ data }) })
      }
      if (urlStr.includes('/ai/trade_plan')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ data: mockAiSuccess }) })
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`))
    }) as unknown as typeof fetch

    vi.stubGlobal('fetch', fetchMock)
    useCockpitStore.setState({ selectedTicker: 'NVDA' })

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    renderWidgetWith(qc)

    // Wait for initial decision to load (hash = abc123de456789)
    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())

    // Open AI section — first fetch (count=1)
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))
    await waitFor(() => expect(screen.getByTestId('ai-plan-result')).toBeInTheDocument())

    const aiCount1 = (fetchMock.mock.calls as Array<[string]>).filter(
      ([url]) => url.includes('/ai/trade_plan'),
    ).length
    expect(aiCount1).toBe(1)

    // Recompute → decisionQuery.refetch() → call 2 returns mockDecision2 (new hash)
    fireEvent.click(screen.getByText('↻ Recompute'))

    // Wait for AI to auto-refetch (queryKey changed because deterministicHash changed)
    await waitFor(() => {
      const aiCalls = (fetchMock.mock.calls as Array<[string, RequestInit]>).filter(
        ([url]) => url.includes('/ai/trade_plan'),
      )
      expect(aiCalls.length).toBe(2)
    })

    // Verify second AI call body contains the new deterministicHash
    const aiCalls = (fetchMock.mock.calls as Array<[string, RequestInit]>).filter(
      ([url]) => url.includes('/ai/trade_plan'),
    )
    const lastBody = JSON.parse(aiCalls[1][1]!.body as string) as {
      input: Record<string, unknown>
    }
    expect(lastBody.input.deterministicHash).toBe('xyz789ab012345')
  })
})

describe('T13 – earningsRisk null → AI request still 200 (no client validation drop)', () => {
  it('decision.earningsRisk=null is forwarded as null in body.input; success path renders memo', async () => {
    let capturedInput: Record<string, unknown> | null = null
    vi.stubGlobal(
      'fetch',
      makeRoutedFetch({
        decisionSequence: [{ earningsRisk: null }],
        onAiCall: (b) => {
          capturedInput = b.input
        },
      }),
    )
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    renderWidget()

    await waitFor(() => expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-plan-trigger'))
    await waitFor(() => expect(capturedInput).not.toBeNull())

    // earningsRisk null is preserved literally (not omitted, not stringified)
    expect(capturedInput).toHaveProperty('earningsRisk', null)
    expect(Object.keys(capturedInput!).length).toBe(12)

    // Success path completes — memo + Guardrail passed render
    await waitFor(() => {
      expect(screen.getByTestId('ai-plan-memo')).toBeInTheDocument()
      expect(screen.getByTestId('ai-plan-guardrail-passed')).toBeInTheDocument()
    })
  })
})

// ── §C — AI Contradictions ────────────────────────────────────────────────────

const mockSetupItem: SetupItem = {
  ticker: 'NVDA',
  stockName: 'NVIDIA Corp',
  setupType: 'BREAKOUT',
  setupQuality: 'A',
  entryPrice: 850,
  stopPrice: 820,
  target2r: 910,
  target3r: 940,
  distanceToEntryPct: 0.5,
  rewardRisk: 2.0,
  rsPercentile: 85.2,
  volumeStatus: null,
  trendScore: 4,
  earningsRisk: 'SAFE',
  readySignal: true,
  suggestedAction: 'enter',
  scanDate: '2026-04-28',
}

const mockSetupMonitorData: SetupMonitorData = {
  summary: { total: 1, ready: 1, near: 0, extended: 0, broken: 0, none: 0 },
  items: [mockSetupItem],
}

const mockRegimeData: CockpitRegimeData = {
  date: '2026-04-28',
  regime: 'CONSTRUCTIVE',
  marketScore: 72,
  subscores: {
    spyTrend: 70,
    qqqTrend: 75,
    iwmBreadth: 65,
    sectorParticipation: 68,
    riskAppetite: 72,
    volatilityStress: 80,
  },
  allowedExposurePct: 80,
  singleTradeRiskPct: 1.0,
  preferredSetups: ['BREAKOUT', 'CAPITULATION'],
  avoidSetups: ['EXTENDED'],
  indices: [],
  sectors: [],
  computedAt: '2026-04-28T09:00:00Z',
}

const mockContradictionsSuccess = {
  memoId: 2,
  taskType: 'contradiction_detector',
  schemaVersion: 'v1',
  output: {
    contradictions: [
      { type: 'earnings_risk', severity: 'HIGH', text: 'Earnings in 14 days — major risk' },
      { type: 'reward_risk', severity: 'MEDIUM', text: 'R:R at 2.0 — borderline threshold' },
      { type: 'trend_quality', severity: 'LOW', text: 'Trend score is 4, minimum acceptable' },
    ],
    recommendation: 'Reduce size to 50% given earnings proximity',
  },
  meta: {
    modelUsed: 'gpt-4o-mini',
    tier: 'default',
    tokensIn: 100,
    tokensOut: 150,
    costUsd: 0.001,
    latencyMs: 500,
    cacheHit: false,
  },
}

function renderWithContradictionCache(
  fetchImpl: (url: string, init?: RequestInit) => Promise<unknown>,
  opts: { noSetupForTicker?: boolean } = {},
) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })

  const setupData: SetupMonitorData = opts.noSetupForTicker
    ? { summary: { total: 0, ready: 0, near: 0, extended: 0, broken: 0, none: 0 }, items: [] }
    : mockSetupMonitorData
  qc.setQueryData(['cockpit-setup-monitor', 'all'], setupData)
  qc.setQueryData(['cockpit-regime'], mockRegimeData)

  vi.stubGlobal('fetch', fetchImpl as typeof fetch)
  useCockpitStore.setState({ selectedTicker: 'NVDA' })

  return render(
    <QueryClientProvider client={qc}>
      <DecisionPanelWidget />
    </QueryClientProvider>,
  )
}

function makeContradictionFetch(opts: {
  aiStatus?: 200 | 409 | 502
  aiPending?: boolean
  aiMeta?: { cacheHit?: boolean; modelUsed?: string }
  aiOutput?: { contradictions: unknown[]; recommendation: string }
} = {}) {
  const { aiStatus = 200, aiPending = false, aiMeta, aiOutput } = opts
  return (url: string) => {
    const urlStr = url as string
    if (urlStr.includes('/cockpit/decision/')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ data: mockDecision }) })
    }
    if (urlStr.includes('/ai/contradiction_detector')) {
      if (aiPending) return new Promise(() => {})
      if (aiStatus === 409) {
        return Promise.resolve({
          ok: false, status: 409,
          json: () => Promise.resolve({ error: { code: 'AI_GUARDRAIL_VIOLATION', message: 'guardrail' } }),
        })
      }
      if (aiStatus === 502) {
        return Promise.resolve({
          ok: false, status: 502,
          json: () => Promise.resolve({ error: { code: 'AI_PROVIDER_ERROR', message: 'provider error' } }),
        })
      }
      const meta = aiMeta
        ? { ...mockContradictionsSuccess.meta, ...aiMeta }
        : mockContradictionsSuccess.meta
      const output = aiOutput ?? mockContradictionsSuccess.output
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: { ...mockContradictionsSuccess, output, meta } }),
      })
    }
    return Promise.reject(new Error(`Unexpected URL: ${urlStr}`))
  }
}

describe('C1 – closed: trigger renders enabled, no AI fetch', () => {
  it('shows "Generate AI Contradictions" button; /ai/contradiction_detector not called', async () => {
    const fetchMock = vi.fn(makeContradictionFetch())
    renderWithContradictionCache(fetchMock)

    await waitFor(() => {
      expect(screen.getByTestId('ai-contradictions-trigger')).toBeInTheDocument()
    })

    const trigger = screen.getByTestId('ai-contradictions-trigger')
    expect(trigger).not.toBeDisabled()
    expect(trigger.textContent).toContain('Generate AI Contradictions')

    const aiCalls = (fetchMock.mock.calls as Array<[string]>).filter(
      ([url]) => url.includes('/ai/contradiction_detector'),
    )
    expect(aiCalls.length).toBe(0)
  })
})

describe('C2 – click trigger → loading → skeletons visible', () => {
  it('shows skeletons while AI fetch is pending', async () => {
    const fetchMock = vi.fn(makeContradictionFetch({ aiPending: true }))
    renderWithContradictionCache(fetchMock)

    await waitFor(() => expect(screen.getByTestId('ai-contradictions-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-contradictions-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-contradictions-loading')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ai-contradictions-skeleton-list')).toBeInTheDocument()
    expect(screen.getByTestId('ai-contradictions-skeleton-rec')).toBeInTheDocument()
  })
})

describe('C3 – success with 3 contradictions: HIGH / MEDIUM / LOW', () => {
  it('renders list items with severity tags and recommendation', async () => {
    const fetchMock = vi.fn(makeContradictionFetch())
    renderWithContradictionCache(fetchMock)

    await waitFor(() => expect(screen.getByTestId('ai-contradictions-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-contradictions-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-contradictions-result')).toBeInTheDocument()
    })

    // 3 list items
    expect(screen.getByTestId('ai-contradictions-item-0')).toBeInTheDocument()
    expect(screen.getByTestId('ai-contradictions-item-1')).toBeInTheDocument()
    expect(screen.getByTestId('ai-contradictions-item-2')).toBeInTheDocument()

    // Severity tags
    expect(screen.getByTestId('ai-contradictions-severity-0').textContent).toBe('HIGH')
    expect(screen.getByTestId('ai-contradictions-severity-1').textContent).toBe('MEDIUM')
    expect(screen.getByTestId('ai-contradictions-severity-2').textContent).toBe('LOW')

    // Recommendation line
    expect(screen.getByTestId('ai-contradictions-recommendation').textContent).toContain(
      'Recommendation: Reduce size to 50% given earnings proximity',
    )

    // Cache badge shows Generated
    expect(screen.getByTestId('ai-contradictions-cache-badge').textContent).toContain('Generated')
  })
})

describe('C4 – success empty: contradictions=[] → only recommendation line', () => {
  it('no list items; shows recommendation only', async () => {
    const fetchMock = vi.fn(
      makeContradictionFetch({
        aiOutput: { contradictions: [], recommendation: 'No major contradictions' },
      }),
    )
    renderWithContradictionCache(fetchMock)

    await waitFor(() => expect(screen.getByTestId('ai-contradictions-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-contradictions-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-contradictions-result')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('ai-contradictions-item-0')).not.toBeInTheDocument()
    expect(screen.getByTestId('ai-contradictions-recommendation').textContent).toContain(
      'No major contradictions',
    )
  })
})

describe('C5 – error 502 → "AI 暂不可用" + close back to trigger', () => {
  it('shows error message; close button returns to closed state', async () => {
    const fetchMock = vi.fn(makeContradictionFetch({ aiStatus: 502 }))
    renderWithContradictionCache(fetchMock)

    await waitFor(() => expect(screen.getByTestId('ai-contradictions-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-contradictions-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-contradictions-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ai-contradictions-error').textContent).toContain('AI 暂不可用')

    // Close → back to trigger
    fireEvent.click(screen.getByTestId('ai-contradictions-error-close'))
    await waitFor(() => {
      expect(screen.getByTestId('ai-contradictions-trigger')).toBeInTheDocument()
    })
  })
})

describe('C6 – error 409 → red guardrail banner', () => {
  it('shows red "AI 输出被拦截" banner', async () => {
    const fetchMock = vi.fn(makeContradictionFetch({ aiStatus: 409 }))
    renderWithContradictionCache(fetchMock)

    await waitFor(() => expect(screen.getByTestId('ai-contradictions-trigger')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ai-contradictions-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-contradictions-guardrail-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ai-contradictions-guardrail-error').textContent).toContain(
      'AI 输出被拦截',
    )
  })
})

describe('C7 – setupMonitor 无当前 ticker → trigger disabled', () => {
  it('trigger button is disabled with title text when ticker not in setup list', async () => {
    const fetchMock = vi.fn(makeContradictionFetch())
    renderWithContradictionCache(fetchMock, { noSetupForTicker: true })

    await waitFor(() => {
      expect(screen.getByTestId('ai-contradictions-trigger')).toBeInTheDocument()
    })

    const trigger = screen.getByTestId('ai-contradictions-trigger')
    expect(trigger).toBeDisabled()
    expect(trigger).toHaveAttribute('title', '需 Setup Monitor 数据')
  })
})

describe('C8 – integration: trade_plan + contradictions dividers both rendered', () => {
  it('data loaded → ai-plan-divider and ai-contradictions-divider both in DOM', async () => {
    const fetchMock = vi.fn(makeContradictionFetch())
    renderWithContradictionCache(fetchMock)

    await waitFor(() => {
      expect(screen.getByTestId('ai-plan-divider')).toBeInTheDocument()
      expect(screen.getByTestId('ai-contradictions-divider')).toBeInTheDocument()
    })

    // Both trigger buttons visible (both sections closed by default)
    expect(screen.getByTestId('ai-plan-trigger')).toBeInTheDocument()
    expect(screen.getByTestId('ai-contradictions-trigger')).toBeInTheDocument()
  })
})

// ── C1–C6: RepricingChipRow (F218-d7b) ─────────────────────────────────────

// Multi-endpoint fetch mock: routes /cockpit/decision/ and /cockpit/repricing-triggers/
function makeChipFetch(opts: {
  repricingTriggers?: object[]
  repricingStatus?: 200 | 422 | 'pending'
}) {
  return vi.fn((url: string) => {
    if ((url as string).includes('/cockpit/repricing-triggers/')) {
      if (opts.repricingStatus === 'pending') return new Promise(() => {}) // never resolves
      if (opts.repricingStatus === 422) {
        return Promise.resolve({
          ok: false,
          status: 422,
          json: () => Promise.resolve({ error: { code: 'ERR', message: 'err' } }),
        })
      }
      const data = { ticker: 'NVDA', triggers: opts.repricingTriggers ?? [] }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ data }) })
    }
    if ((url as string).includes('/cockpit/decision/')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ data: mockDecision }) })
    }
    return Promise.reject(new Error(`Unexpected URL: ${url}`))
  }) as unknown as typeof fetch
}

describe('C1 – ticker=null → chip area not rendered', () => {
  it('empty state shows; no repricing chip in DOM', () => {
    vi.stubGlobal('fetch', vi.fn())
    useCockpitStore.setState({ selectedTicker: null })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    renderWidgetWith(qc)
    expect(screen.getByText(/请在 Setup Monitor/)).toBeInTheDocument()
    expect(document.querySelector('[data-repricing-chip]')).toBeNull()
  })
})

describe('C2 – ticker="NVDA" + 2 triggers → 2 chips rendered with correct colors', () => {
  it('chip row shows 2 chips matching token vars', async () => {
    const triggers = [
      {
        triggerType: 'EARNINGS_ACCEL',
        detectedDate: '2026-05-15',
        confidence: 0.8,
        evidence: { epsYoyGrowth: [78], revenueYoyGrowth: [32], quarters: ['Q1'] },
        computedAt: '2026-05-20T22:40:00Z',
      },
      {
        triggerType: 'MARGIN_EXPANSION',
        detectedDate: '2026-05-15',
        confidence: 0.75,
        evidence: {
          grossMarginTrend: [0.40, 0.49],
          fcfMarginTrend: [0.10, 0.15],
          quarters: ['Q1'],
          triggerMetric: 'gross_margin',
          expansionBp: 900,
        },
        computedAt: '2026-05-20T22:40:00Z',
      },
    ]
    vi.stubGlobal('fetch', makeChipFetch({ repricingTriggers: triggers }))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    renderWidgetWith(qc)

    await waitFor(() => {
      expect(document.querySelectorAll('[data-repricing-chip]')).toHaveLength(2)
    })

    const chips = Array.from(document.querySelectorAll('[data-repricing-chip]')) as HTMLElement[]
    const chipTypes = chips.map((c) => c.getAttribute('data-repricing-chip'))
    expect(chipTypes).toContain('EARNINGS_ACCEL')
    expect(chipTypes).toContain('MARGIN_EXPANSION')

    const earningsChip = chips.find((c) => c.getAttribute('data-repricing-chip') === 'EARNINGS_ACCEL')!
    expect(earningsChip.style.color).toBe('var(--color-trigger-earnings-accel)')
  })
})

describe('C3 – ticker="AAPL" + empty triggers → chip area null, decision normal', () => {
  it('no chips rendered; decision card body still renders', async () => {
    vi.stubGlobal('fetch', makeChipFetch({ repricingTriggers: [] }))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    renderWidgetWith(qc)

    await waitFor(() => screen.getByText('850.00'))

    expect(document.querySelector('[data-repricing-chip]')).toBeNull()
    expect(screen.getByText('850.00')).toBeInTheDocument()
  })
})

describe('C4 – repricing API loading → chip area null (does not block SkeletonCard)', () => {
  it('decision loading shows skeleton; chip row absent', async () => {
    vi.stubGlobal('fetch', makeChipFetch({ repricingStatus: 'pending' }))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    renderWidgetWith(qc)

    // Decision also pending → skeleton is shown
    await waitFor(() => {
      expect(document.querySelector('[data-slot="skeleton"]')).not.toBeNull()
    })
    expect(document.querySelector('[data-repricing-chip]')).toBeNull()
  })
})

describe('C5 – repricing API error → chip area null (silent)', () => {
  it('decision card renders normally; no chips on repricing 422', async () => {
    vi.stubGlobal('fetch', makeChipFetch({ repricingStatus: 422 }))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    renderWidgetWith(qc)

    await waitFor(() => screen.getByText('850.00'))

    expect(document.querySelector('[data-repricing-chip]')).toBeNull()
    expect(screen.getByText('850.00')).toBeInTheDocument()
  })
})

describe('C6 – hover chip → tooltip shows evidence summary', () => {
  it('EarningsAccel chip tooltip content contains "eps yoy 78%"', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()

    const triggers = [
      {
        triggerType: 'EARNINGS_ACCEL',
        detectedDate: '2026-05-15',
        confidence: 0.8,
        evidence: { epsYoyGrowth: [78], revenueYoyGrowth: [32], quarters: ['Q1'] },
        computedAt: '2026-05-20T22:40:00Z',
      },
    ]
    vi.stubGlobal('fetch', makeChipFetch({ repricingTriggers: triggers }))
    useCockpitStore.setState({ selectedTicker: 'NVDA' })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    renderWidgetWith(qc)

    // Wait for chip to appear
    const chip = await waitFor(() => {
      const el = document.querySelector('[data-repricing-chip="EARNINGS_ACCEL"]')
      expect(el).not.toBeNull()
      return el as HTMLElement
    })

    // Hover to open Radix tooltip (fires pointerenter; tooltip opens after delayDuration)
    await user.hover(chip)

    // Tooltip renders with role="tooltip" in a Radix portal
    const tooltip = await screen.findByRole('tooltip', {}, { timeout: 2000 })
    expect(tooltip.textContent).toContain('eps yoy 78%')
  })
})
