/**
 * ArticleDetailWidget auto-translate tests (AD1-AD13).
 * Ported from the former ArticleModal (F213-b, AM1-AM14) after the article
 * detail + auto-translate flow moved out of the full-screen modal into an
 * inline News-page widget. Modal-only cases (dialog role, ESC/onClose) are
 * replaced by the widget empty-state case (AD1).
 */
import { render, screen, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, beforeEach } from 'vitest'
import { ArticleDetailWidget } from '../ArticleDetailWidget'
import type { NewsArticle } from '@/types/news'

// ── Hoisted mocks ─────────────────────────────────────────────────────────────

const { mockTranslateArticle, mockToastError, mockMarkAsRead } = vi.hoisted(() => ({
  mockTranslateArticle: vi.fn(),
  mockToastError: vi.fn(),
  mockMarkAsRead: vi.fn(),
}))

vi.mock('@/lib/api/translateArticle', () => ({
  translateArticle: mockTranslateArticle,
}))

vi.mock('sonner', () => ({
  toast: { error: mockToastError },
}))

vi.mock('@/store/useReadArticlesStore', () => ({
  useReadArticlesStore: (selector: (s: { markAsRead: typeof mockMarkAsRead }) => unknown) =>
    selector({ markAsRead: mockMarkAsRead }),
}))

// ── Fixtures ──────────────────────────────────────────────────────────────────

const ARTICLE_A: NewsArticle = {
  title: 'Apple Q1 Earnings Beat',
  publishedAt: '2026-04-29T10:00:00Z',
  contentHtml: '<p>Apple reported strong Q1 <b>earnings</b>.</p>',
  symbols: ['AAPL', 'QQQ'],
  imageUrl: null,
  url: 'https://example.com/apple-q1',
  author: 'Jane Doe',
  site: 'MarketWatch',
}

const ARTICLE_B: NewsArticle = {
  title: 'Fed Holds Rates',
  publishedAt: '2026-04-28T08:00:00Z',
  contentHtml: '<p>Federal Reserve holds rates steady.</p>',
  symbols: ['SPY'],
  imageUrl: null,
  url: 'https://example.com/fed-rates',
  author: null,
  site: null,
}

const SUCCESS_NO_CACHE = {
  memoId: 1,
  taskType: 'translate_article',
  schemaVersion: 'v1',
  output: {
    titleZh: '苹果Q1财报超预期',
    contentZh: '苹果报告了强劲的Q1业绩。\n\n分析师预期被超越。',
  },
  meta: {
    modelUsed: 'deepseek-v3',
    tier: 'override',
    tokensIn: 100,
    tokensOut: 50,
    costUsd: 0.001,
    latencyMs: 800,
    cacheHit: false,
  },
}

const SUCCESS_CACHE_HIT = {
  ...SUCCESS_NO_CACHE,
  meta: { ...SUCCESS_NO_CACHE.meta, cacheHit: true },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeQC(gcTime = 0) {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime, retryDelay: 0 } },
  })
}

function renderWidget(
  article: NewsArticle | null,
  {
    qc = makeQC(),
    onSelectTicker = vi.fn(),
  }: {
    qc?: QueryClient
    onSelectTicker?: ReturnType<typeof vi.fn>
  } = {},
) {
  const result = render(
    <QueryClientProvider client={qc}>
      <ArticleDetailWidget article={article} onSelectTicker={onSelectTicker} />
    </QueryClientProvider>,
  )
  return { ...result, onSelectTicker, qc }
}

beforeEach(() => {
  mockTranslateArticle.mockReset()
  mockToastError.mockReset()
  mockMarkAsRead.mockReset()
})

// ── AD1: empty state ──────────────────────────────────────────────────────────

describe('AD1: article=null → empty-state prompt, no translate call', () => {
  it('renders the empty-state hint and does not call translateArticle', () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderWidget(null)

    expect(screen.getByText('点击左侧新闻查看详情')).toBeInTheDocument()
    expect(mockTranslateArticle).not.toHaveBeenCalled()
  })
})

// ── AD2: basic render ─────────────────────────────────────────────────────────

describe('AD2: article provided → title + ticker buttons', () => {
  it('renders the title text and ticker buttons', () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderWidget(ARTICLE_A)

    expect(screen.getByText('Apple Q1 Earnings Beat')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'AAPL' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'QQQ' })).toBeInTheDocument()
  })
})

// ── AD3-AD4: HTML stripping ───────────────────────────────────────────────────

describe('AD3: contentHtml with <script> → translateArticle receives stripped text', () => {
  it('strips script tags before passing contentText to translateArticle', async () => {
    const maliciousArticle: NewsArticle = {
      ...ARTICLE_A,
      contentHtml: '<script>alert("xss")</script><p>Clean content here.</p>',
    }
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderWidget(maliciousArticle)

    await waitFor(() => expect(mockTranslateArticle).toHaveBeenCalled())
    const { contentText } = mockTranslateArticle.mock.calls[0][0] as { contentText: string }
    expect(contentText).not.toContain('<script>')
    expect(contentText).not.toContain('alert')
    expect(contentText).toContain('Clean content here.')
  })
})

describe('AD4: empty contentHtml → translateArticle not called (enabled=false)', () => {
  it('skips the query when contentHtml is empty', () => {
    const emptyArticle: NewsArticle = { ...ARTICLE_A, contentHtml: '' }
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderWidget(emptyArticle)

    expect(mockTranslateArticle).not.toHaveBeenCalled()
  })
})

// ── AD5-AD6: loading state ────────────────────────────────────────────────────

describe('AD5: loading — shows original title + "正在翻译..." + spinner', () => {
  it('renders loading indicator while translateArticle is pending', () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderWidget(ARTICLE_A)

    expect(screen.getByText('Apple Q1 Earnings Beat')).toBeInTheDocument()
    expect(screen.getByText('正在翻译...')).toBeInTheDocument()
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
  })
})

describe('AD6: translateArticle called once on first render with correct args', () => {
  it('called exactly once with {title, contentText}', async () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderWidget(ARTICLE_A)

    await waitFor(() => expect(mockTranslateArticle).toHaveBeenCalledTimes(1))
    const callArg = mockTranslateArticle.mock.calls[0][0] as {
      title: string
      contentText: string
    }
    expect(callArg.title).toBe('Apple Q1 Earnings Beat')
    expect(callArg.contentText).toBe('Apple reported strong Q1 earnings.')
  })
})

// ── AD7-AD8: success state ────────────────────────────────────────────────────

describe('AD7: resolve → titleZh replaces title, contentZh rendered as <p> segments', () => {
  it('shows translated title and split paragraphs', async () => {
    mockTranslateArticle.mockResolvedValue(SUCCESS_NO_CACHE)
    renderWidget(ARTICLE_A)

    await waitFor(() => expect(screen.getByText('苹果Q1财报超预期')).toBeInTheDocument())
    expect(screen.getByText('苹果报告了强劲的Q1业绩。')).toBeInTheDocument()
    expect(screen.getByText('分析师预期被超越。')).toBeInTheDocument()
    expect(screen.queryByText('正在翻译...')).toBeNull()
  })
})

describe('AD8: meta.cacheHit=true → shows "已缓存" badge', () => {
  it('shows cache badge when cacheHit is true', async () => {
    mockTranslateArticle.mockResolvedValue(SUCCESS_CACHE_HIT)
    renderWidget(ARTICLE_A)

    await waitFor(() => expect(screen.getByText('已缓存')).toBeInTheDocument())
  })
})

// ── AD9-AD10: error state ─────────────────────────────────────────────────────

describe('AD9: reject → original title kept, dompurify path, "翻译失败" shown', () => {
  it('falls back to original title and HTML content on error', async () => {
    mockTranslateArticle.mockRejectedValue(new Error('Network error'))
    renderWidget(ARTICLE_A)

    await waitFor(() => expect(screen.getByText('翻译失败，显示原文')).toBeInTheDocument())
    expect(screen.getByText('Apple Q1 Earnings Beat')).toBeInTheDocument()
    expect(document.querySelector('.article-content')).toBeInTheDocument()
    expect(screen.queryByText('苹果Q1财报超预期')).toBeNull()
  })
})

describe('AD10: error → toast.error fired exactly once', () => {
  it('calls toast.error once with the failure message', async () => {
    mockTranslateArticle.mockRejectedValue(new Error('Network error'))
    renderWidget(ARTICLE_A)

    await waitFor(() => expect(mockToastError).toHaveBeenCalledTimes(1))
    expect(mockToastError).toHaveBeenCalledWith('文章翻译失败，已显示原文')
  })
})

// ── AD11: markAsRead ──────────────────────────────────────────────────────────

describe('AD11: opening an article marks it as read', () => {
  it('calls markAsRead once when an article is shown', async () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderWidget(ARTICLE_A)

    await waitFor(() => expect(mockMarkAsRead).toHaveBeenCalledTimes(1))
  })
})

// ── AD12: cache reuse ─────────────────────────────────────────────────────────

describe('AD12: same article re-show → translateArticle called only once (react-query cache)', () => {
  it('second mount uses in-memory cache without re-calling translateArticle', async () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    })
    mockTranslateArticle.mockResolvedValue(SUCCESS_NO_CACHE)

    const { unmount } = renderWidget(ARTICLE_A, { qc })
    await waitFor(() => expect(screen.getByText('苹果Q1财报超预期')).toBeInTheDocument())
    unmount()

    mockTranslateArticle.mockClear()
    renderWidget(ARTICLE_A, { qc })
    await act(async () => {})
    expect(mockTranslateArticle).toHaveBeenCalledTimes(0)
  })
})

// ── AD13: article switch → two calls with correct args ───────────────────────

describe('AD13: switching article A→B → two translateArticle calls with distinct args', () => {
  it('calls translateArticle once for A and once for B', async () => {
    const qc = makeQC(0)
    mockTranslateArticle.mockResolvedValue(SUCCESS_NO_CACHE)

    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <ArticleDetailWidget article={ARTICLE_A} />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(mockTranslateArticle).toHaveBeenCalledTimes(1))
    expect(mockTranslateArticle.mock.calls[0][0]).toMatchObject({ title: 'Apple Q1 Earnings Beat' })

    rerender(
      <QueryClientProvider client={qc}>
        <ArticleDetailWidget article={ARTICLE_B} />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(mockTranslateArticle).toHaveBeenCalledTimes(2))
    expect(mockTranslateArticle.mock.calls[1][0]).toMatchObject({ title: 'Fed Holds Rates' })
  })
})
