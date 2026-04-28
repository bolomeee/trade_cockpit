import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, beforeEach } from 'vitest'
import { ApiError } from '@/lib/api/client'
import {
  AiNewsSummaryBar,
  stripHtml,
  sortByPublishedDesc,
  articlesHash,
  buildSummarizerArticles,
} from '../AiNewsSummaryBar'
import type { NewsArticle } from '@/types/news'

// ── Hoisted mocks ─────────────────────────────────────────────────────────────

const { mockCallAiTask, mockUseNewsArticles, mockSetSelectedSymbol } = vi.hoisted(() => ({
  mockCallAiTask: vi.fn(),
  mockUseNewsArticles: vi.fn(),
  mockSetSelectedSymbol: vi.fn(),
}))

vi.mock('@/cockpit/lib/api/aiApi', () => ({ callAiTask: mockCallAiTask }))
vi.mock('@/hooks/useNewsArticles', () => ({ useNewsArticles: mockUseNewsArticles }))
vi.mock('@/store/useAppStore', () => ({
  useAppStore: (selector: (s: { setSelectedSymbol: typeof mockSetSelectedSymbol }) => unknown) =>
    selector({ setSelectedSymbol: mockSetSelectedSymbol }),
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
})

// ── Component tests C1-C8 ─────────────────────────────────────────────────────

describe('AiNewsSummaryBar — component', () => {
  it('C1: renders trigger button when closed', () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockReturnValue(new Promise(() => {}))

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })

    expect(screen.getByTestId('ai-news-summary-trigger')).toBeInTheDocument()
    expect(screen.queryByTestId('ai-news-summary-loading')).toBeNull()
  })

  it('C2: renders skeleton during loading after trigger click', async () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockReturnValue(new Promise(() => {})) // never resolves

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })
    fireEvent.click(screen.getByTestId('ai-news-summary-trigger'))

    await waitFor(() =>
      expect(screen.getByTestId('ai-news-summary-skeleton-summary')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('ai-news-summary-skeleton-risks')).toBeInTheDocument()
  })

  it('C3: success — catalystSummary, sentiment badge, tickers, risks all render', async () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockResolvedValue(MOCK_SUCCESS_RESPONSE)

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })
    fireEvent.click(screen.getByTestId('ai-news-summary-trigger'))

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
    fireEvent.click(screen.getByTestId('ai-news-summary-trigger'))

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
    fireEvent.click(screen.getByTestId('ai-news-summary-trigger'))

    await waitFor(() =>
      expect(screen.getByTestId('ai-news-summary-result')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('ai-news-summary-tickers')).toBeNull()
  })

  it('C6: error 502 → shows "AI 暂不可用" + close returns to trigger', async () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockRejectedValue(new ApiError('UNKNOWN', 'server error', 502))

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })
    fireEvent.click(screen.getByTestId('ai-news-summary-trigger'))

    await waitFor(() =>
      expect(screen.getByTestId('ai-news-summary-error')).toBeInTheDocument(),
    )
    expect(screen.getByText('AI 暂不可用')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('ai-news-summary-error-close'))
    expect(screen.getByTestId('ai-news-summary-trigger')).toBeInTheDocument()
  })

  it('C7: error 409 → shows "AI 输出被拦截" guardrail banner', async () => {
    mockUseNewsArticles.mockReturnValue({ data: MOCK_ARTICLES })
    mockCallAiTask.mockRejectedValue(new ApiError('GUARDRAIL_VIOLATION', 'banned phrase', 409))

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })
    fireEvent.click(screen.getByTestId('ai-news-summary-trigger'))

    await waitFor(() =>
      expect(screen.getByTestId('ai-news-summary-guardrail-error')).toBeInTheDocument(),
    )
    expect(screen.getByText('AI 输出被拦截')).toBeInTheDocument()
  })

  it('C8: articles empty → trigger disabled with title="暂无 news"', () => {
    mockUseNewsArticles.mockReturnValue({ data: [] })

    render(<AiNewsSummaryBar />, { wrapper: makeWrapper() })

    const trigger = screen.getByTestId('ai-news-summary-trigger')
    expect(trigger).toBeDisabled()
    expect(trigger).toHaveAttribute('title', '暂无 news')
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
