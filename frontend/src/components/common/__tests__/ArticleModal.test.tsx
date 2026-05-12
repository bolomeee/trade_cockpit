/**
 * F213-b: ArticleModal auto-translate tests (AM1-AM14)
 * LIB1 is in src/lib/api/__tests__/translateArticle.test.ts — kept separate
 * because AM* tests mock translateArticle at module level, which prevents
 * testing the real function's callAiTask forwarding in the same file.
 */
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, beforeEach } from 'vitest'
import { ArticleModal } from '../ArticleModal'
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

function renderModal(
  article: NewsArticle | null,
  {
    qc = makeQC(),
    onClose = vi.fn(),
    onSelectTicker = vi.fn(),
  }: {
    qc?: QueryClient
    onClose?: ReturnType<typeof vi.fn>
    onSelectTicker?: ReturnType<typeof vi.fn>
  } = {},
) {
  const result = render(
    <QueryClientProvider client={qc}>
      <ArticleModal article={article} onClose={onClose} onSelectTicker={onSelectTicker} />
    </QueryClientProvider>,
  )
  return { ...result, onClose, onSelectTicker, qc }
}

beforeEach(() => {
  mockTranslateArticle.mockReset()
  mockToastError.mockReset()
  mockMarkAsRead.mockReset()
})

// ── AM1-AM3: basic render regression ─────────────────────────────────────────

describe('AM1: article=null → renders nothing', () => {
  it('returns null when article is null', () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    const { container } = renderModal(null)
    expect(container.firstChild).toBeNull()
  })
})

describe('AM2: article provided → dialog + title + tickers', () => {
  it('renders dialog role, title text and ticker buttons', () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderModal(ARTICLE_A)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Apple Q1 Earnings Beat')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'AAPL' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'QQQ' })).toBeInTheDocument()
  })
})

describe('AM3: ESC → onClose', () => {
  it('fires onClose when Escape key is pressed', () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    const { onClose } = renderModal(ARTICLE_A)

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

// ── AM4-AM5: HTML stripping ───────────────────────────────────────────────────

describe('AM4: contentHtml with <script> → translateArticle receives stripped text', () => {
  it('strips script tags before passing contentText to translateArticle', async () => {
    const maliciousArticle: NewsArticle = {
      ...ARTICLE_A,
      contentHtml: '<script>alert("xss")</script><p>Clean content here.</p>',
    }
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderModal(maliciousArticle)

    await waitFor(() => expect(mockTranslateArticle).toHaveBeenCalled())
    const { contentText } = mockTranslateArticle.mock.calls[0][0] as { contentText: string }
    expect(contentText).not.toContain('<script>')
    expect(contentText).not.toContain('alert')
    expect(contentText).toContain('Clean content here.')
  })
})

describe('AM5: empty contentHtml → translateArticle not called (enabled=false)', () => {
  it('skips the query when contentHtml is empty', () => {
    const emptyArticle: NewsArticle = { ...ARTICLE_A, contentHtml: '' }
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderModal(emptyArticle)

    expect(mockTranslateArticle).not.toHaveBeenCalled()
  })
})

// ── AM6-AM8: loading state ────────────────────────────────────────────────────

describe('AM6: loading — shows original title + "正在翻译..." + Loader2', () => {
  it('renders loading indicator while translateArticle is pending', () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderModal(ARTICLE_A)

    // Original title shown during loading
    expect(screen.getByText('Apple Q1 Earnings Beat')).toBeInTheDocument()
    expect(screen.getByText('正在翻译...')).toBeInTheDocument()
    // Loader2 icon rendered (lucide gives it an SVG with the class)
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
  })
})

describe('AM7: loading — ESC still closes the modal', () => {
  it('fires onClose while translateArticle is still pending', () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    const { onClose } = renderModal(ARTICLE_A)

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

describe('AM8: translateArticle called once on first render with correct args', () => {
  it('called exactly once with {title, contentText}', async () => {
    mockTranslateArticle.mockReturnValue(new Promise(() => {}))
    renderModal(ARTICLE_A)

    await waitFor(() => expect(mockTranslateArticle).toHaveBeenCalledTimes(1))
    const callArg = mockTranslateArticle.mock.calls[0][0] as {
      title: string
      contentText: string
    }
    expect(callArg.title).toBe('Apple Q1 Earnings Beat')
    // contentText should be the stripped version of contentHtml
    expect(callArg.contentText).toBe('Apple reported strong Q1 earnings.')
  })
})

// ── AM9-AM10: success state ───────────────────────────────────────────────────

describe('AM9: resolve → titleZh replaces title, contentZh rendered as <p> segments', () => {
  it('shows translated title and split paragraphs', async () => {
    mockTranslateArticle.mockResolvedValue(SUCCESS_NO_CACHE)
    renderModal(ARTICLE_A)

    await waitFor(() => expect(screen.getByText('苹果Q1财报超预期')).toBeInTheDocument())
    // contentZh has \n\n → two <p> elements
    expect(screen.getByText('苹果报告了强劲的Q1业绩。')).toBeInTheDocument()
    expect(screen.getByText('分析师预期被超越。')).toBeInTheDocument()
    // Loading indicator gone
    expect(screen.queryByText('正在翻译...')).toBeNull()
  })
})

describe('AM10: meta.cacheHit=true → shows "已缓存" badge', () => {
  it('shows cache badge when cacheHit is true', async () => {
    mockTranslateArticle.mockResolvedValue(SUCCESS_CACHE_HIT)
    renderModal(ARTICLE_A)

    await waitFor(() => expect(screen.getByText('已缓存')).toBeInTheDocument())
  })
})

// ── AM11-AM12: error state ────────────────────────────────────────────────────

describe('AM11: reject → original title kept, dompurify path, "翻译失败" shown', () => {
  it('falls back to original title and HTML content on error', async () => {
    mockTranslateArticle.mockRejectedValue(new Error('Network error'))
    renderModal(ARTICLE_A)

    await waitFor(() => expect(screen.getByText('翻译失败，显示原文')).toBeInTheDocument())
    // Original title retained
    expect(screen.getByText('Apple Q1 Earnings Beat')).toBeInTheDocument()
    // dompurify-rendered content present (via dangerouslySetInnerHTML)
    expect(document.querySelector('.article-content')).toBeInTheDocument()
    // No translated title
    expect(screen.queryByText('苹果Q1财报超预期')).toBeNull()
  })
})

describe('AM12: error → toast.error fired exactly once', () => {
  it('calls toast.error once with the failure message', async () => {
    mockTranslateArticle.mockRejectedValue(new Error('Network error'))
    renderModal(ARTICLE_A)

    await waitFor(() => expect(mockToastError).toHaveBeenCalledTimes(1))
    expect(mockToastError).toHaveBeenCalledWith('文章翻译失败，已显示原文')
  })
})

// ── AM13: cache reuse ─────────────────────────────────────────────────────────

describe('AM13: same article close+reopen → translateArticle called only once (react-query cache)', () => {
  it('second open uses in-memory cache without re-calling translateArticle', async () => {
    // Use a shared QC with gcTime=Infinity so cache survives unmount
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    })
    mockTranslateArticle.mockResolvedValue(SUCCESS_NO_CACHE)

    // First open
    const { unmount } = renderModal(ARTICLE_A, { qc })
    await waitFor(() => expect(screen.getByText('苹果Q1财报超预期')).toBeInTheDocument())
    unmount()

    // Second open — same article, same QC
    mockTranslateArticle.mockClear()
    renderModal(ARTICLE_A, { qc })
    // Wait a tick then assert not called again
    await act(async () => {})
    expect(mockTranslateArticle).toHaveBeenCalledTimes(0)
  })
})

// ── AM14: article switch → two calls with correct args ───────────────────────

describe('AM14: switching article A→B → two translateArticle calls with distinct args', () => {
  it('calls translateArticle once for A and once for B', async () => {
    const qc = makeQC(0)
    mockTranslateArticle.mockResolvedValue(SUCCESS_NO_CACHE)

    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <ArticleModal article={ARTICLE_A} onClose={vi.fn()} />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(mockTranslateArticle).toHaveBeenCalledTimes(1))
    expect(mockTranslateArticle.mock.calls[0][0]).toMatchObject({ title: 'Apple Q1 Earnings Beat' })

    rerender(
      <QueryClientProvider client={qc}>
        <ArticleModal article={ARTICLE_B} onClose={vi.fn()} />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(mockTranslateArticle).toHaveBeenCalledTimes(2))
    expect(mockTranslateArticle.mock.calls[1][0]).toMatchObject({ title: 'Fed Holds Rates' })
  })
})
