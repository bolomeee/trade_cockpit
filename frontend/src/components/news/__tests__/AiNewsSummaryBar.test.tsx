import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, beforeEach } from 'vitest'
import { ApiError } from '@/lib/api/client'
import { AiNewsSummaryBar } from '../AiNewsSummaryBar'
import {
  stripHtml,
  articlesHash,
  buildSummarizerArticles,
} from '../newsSummaryUtils'
import type { NewsArticle } from '@/types/news'

// ── Hoisted mocks ─────────────────────────────────────────────────────────────

const { mockCallAiTask, mockUseNewsArticles, mockSetSelectedSymbol, mockSetOpen, openState } =
  vi.hoisted(() => ({
    mockCallAiTask: vi.fn(),
    mockUseNewsArticles: vi.fn(),
    mockSetSelectedSymbol: vi.fn(),
    mockSetOpen: vi.fn(),
    openState: { value: true },
  }))

vi.mock('@/cockpit/lib/api/aiApi', () => ({ callAiTask: mockCallAiTask }))
vi.mock('@/hooks/useNewsArticles', () => ({ useNewsArticles: mockUseNewsArticles }))
// Component is store-driven (open state lives in the store; the trigger button
// now lives in TopNav). Drive `aiNewsSummaryOpen` via openState.value per test.
vi.mock('@/store/useAppStore', () => ({
  useAppStore: (
    selector: (s: {
      aiNewsSummaryOpen: boolean
      setAiNewsSummaryOpen: typeof mockSetOpen
      setSelectedSymbol: typeof mockSetSelectedSymbol
    }) => unknown,
  ) =>
    selector({
      aiNewsSummaryOpen: openState.value,
      setAiNewsSummaryOpen: mockSetOpen,
      setSelectedSymbol: mockSetSelectedSymbol,
    }),
}))

// ── Fixtures ──────────────────────────────────────────────────────────────────

const MOCK_ARTICLES: NewsArticle[] = [
  {
    title: 'AAPL Q1 Earnings Beat',
    publishedAt: '2026-04-29T10:00:00Z',
    contentHtml: '<p>Apple reported strong Q1 earnings.</p>',
    symbols: ['AAPL'],
    imageUrl: null,
    url: null,
    author: null,
    site: null,
  },
  {
    title: 'Fed Holds Rates',
    publishedAt: '2026-04-28T08:00:00Z',
    contentHtml: '<p>Federal Reserve holds rates steady.</p>',
    symbols: ['SPY', 'QQQ'],
    imageUrl: null,
    url: null,
    author: null,
    site: null,
  },
]

const MOCK_SUCCESS_RESPONSE = {
  memoId: 1,
  taskType: 'news_summarizer',
  schemaVersion: 'v1',
  output: {
    catalystSummary: 'Apple Q1 beat expectations driving tech rally.',
    sentiment: 'positive' as const,
    relevantTickers: ['AAPL', 'QQQ'],
    risks: ['Rate hike concerns', 'China slowdown'],
  },
  meta: {
    modelUsed: 'claude-sonnet-4-6',
    tier: 'default',
    tokensIn: 100,
    tokensOut: 50,
    costUsd: 0.001,
    latencyMs: 1200,
    cacheHit: false,
  },
}

// ── Test wrapper ──────────────────────────────────────────────────────────────

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

beforeEach(() => {
  mockCallAiTask.mockReset()
  mockUseNewsArticles.mockReset()
  mockSetSelectedSymbol.mockReset()
  mockSetOpen.mockReset()
  openState.value = true
})

// ── Component tests C1-C8 ─────────────────────────────────────────────────────

describe('AiNewsSummaryBar — component (store-driven; trigger lives in TopNav)', () => {
  it('C1: renders nothing when closed (aiNewsSummaryOpen=false)', () => {
    openState.value = false
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockReturnValue(new Promise(() => {}))

    const { container } = render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })

    expect(container).toBeEmptyDOMElement()
  })

  it('C2: open → renders skeleton while summarizing', async () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockReturnValue(new Promise(() => {})) // never resolves

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })

    await waitFor(() =>
      expect(screen.getByTestId('ai-news-summary-skeleton-summary')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('ai-news-summary-skeleton-risks')).toBeInTheDocument()
  })

  it('C3: success — catalystSummary, sentiment badge, tickers, risks all render', async () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockResolvedValue(MOCK_SUCCESS_RESPONSE)

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })

    await waitFor(() =>
      expect(screen.getByTestId('ai-news-summary-result')).toBeInTheDocument(),
    )

    expect(screen.getByTestId('ai-news-summary-catalyst')).toHaveTextContent(
      'Apple Q1 beat expectations',
    )
    expect(screen.getByTestId('ai-news-summary-sentiment')).toHaveTextContent('Positive')
    expect(screen.getByTestId('ai-news-summary-tickers')).toBeInTheDocument()
    expect(screen.getByTestId('ai-news-summary-risks')).toBeInTheDocument()
  })

  it('C4: success — risks length 0 hides risks section', async () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockResolvedValue({
      ...MOCK_SUCCESS_RESPONSE,
      output: { ...MOCK_SUCCESS_RESPONSE.output, risks: [] },
    })

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })

    await waitFor(() =>
      expect(screen.getByTestId('ai-news-summary-result')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('ai-news-summary-risks')).toBeNull()
    expect(screen.getByTestId('ai-news-summary-catalyst')).toBeInTheDocument()
  })

  it('C5: success — relevantTickers length 0 hides tickers row', async () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockResolvedValue({
      ...MOCK_SUCCESS_RESPONSE,
      output: { ...MOCK_SUCCESS_RESPONSE.output, relevantTickers: [] },
    })

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })

    await waitFor(() =>
      expect(screen.getByTestId('ai-news-summary-result')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('ai-news-summary-tickers')).toBeNull()
  })

  it('C6: error 502 → shows "AI 暂不可用" + close calls setAiNewsSummaryOpen(false)', async () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockRejectedValue(new ApiError('UNKNOWN', 'server error', 502))

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })

    await waitFor(() =>
      expect(screen.getByTestId('ai-news-summary-error')).toBeInTheDocument(),
    )
    expect(screen.getByText('AI 暂不可用')).toBeInTheDocument()

    // Close now delegates to the store (trigger lives in TopNav)
    fireEvent.click(screen.getByTestId('ai-news-summary-error-close'))
    expect(mockSetOpen).toHaveBeenCalledWith(false)
  })

  it('C7: error 409 → shows "AI 输出被拦截" guardrail banner', async () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockRejectedValue(new ApiError('GUARDRAIL_VIOLATION', 'banned phrase', 409))

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })

    await waitFor(() =>
      expect(screen.getByTestId('ai-news-summary-guardrail-error')).toBeInTheDocument(),
    )
    expect(screen.getByText('AI 输出被拦截')).toBeInTheDocument()
  })

  it('C8: open but articles empty → no AI call, nothing rendered', () => {
    mockUseNewsArticles.mockReturnValue({ data: [] })

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })

    expect(mockCallAiTask).not.toHaveBeenCalled()
    expect(screen.queryByTestId('ai-news-summary-result')).toBeNull()
    expect(screen.queryByTestId('ai-news-summary-skeleton-summary')).toBeNull()
  })
})

// ── Helper unit tests ─────────────────────────────────────────────────────────

describe('stripHtml', () => {
  it('returns empty string for empty / falsy input', () => {
    expect(stripHtml('')).toBe('')
    expect(stripHtml(null as unknown as string)).toBe('')
  })

  it('strips HTML tags and trims whitespace', () => {
    expect(stripHtml('<p>  hello <b>world</b>  </p>')).toBe('hello world')
  })

  it('truncates output to 2000 chars', () => {
    const html = '<p>' + 'x'.repeat(3000) + '</p>'
    expect(stripHtml(html).length).toBe(2000)
  })
})

describe('sortByPublishedDesc + slice via buildSummarizerArticles', () => {
  it('sorts articles by publishedAt descending and slices to 30', () => {
    const articles: NewsArticle[] = Array.from({ length: 35 }, (_, i) => ({
      title: `Article ${i}`,
      publishedAt: `2026-04-${String(i + 1).padStart(2, '0')}T00:00:00Z`,
      contentHtml: '',
      symbols: [],
      imageUrl: null,
      url: null,
      author: null,
      site: null,
    }))

    const result = buildSummarizerArticles(articles)
    expect(result).toHaveLength(30)
    // First item should be the one with the latest publishedAt
    expect(result[0].publishedAt).toBe('2026-04-35T00:00:00Z')
    // Items should be in descending order
    for (let i = 1; i < result.length; i++) {
      expect(result[i].publishedAt <= result[i - 1].publishedAt).toBe(true)
    }
  })
})

describe('articlesHash', () => {
  it('returns the same hash for the same input', async () => {
    const items = buildSummarizerArticles(MOCK_ARTICLES)
    const h1 = await articlesHash(items)
    const h2 = await articlesHash(items)
    expect(h1).toBe(h2)
    expect(h1).toHaveLength(16)
  })

  it('returns different hashes for different inputs', async () => {
    const items1 = buildSummarizerArticles(MOCK_ARTICLES)
    const items2 = buildSummarizerArticles([{ ...MOCK_ARTICLES[0], title: 'Different Title' }])
    const h1 = await articlesHash(items1)
    const h2 = await articlesHash(items2)
    expect(h1).not.toBe(h2)
  })
})
