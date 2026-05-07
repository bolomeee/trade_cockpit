/**
 * F213-b: ArticleModal auto-translate tests
 * LIB1 is in src/lib/api/__tests__/translateArticle.test.ts (separate file
 * because AM* tests mock translateArticle at module level, which would prevent
 * testing the real function's callAiTask forwarding in the same file).
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

const TRANSLATE_SUCCESS = {
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

// ── Test wrapper ──────────────────────────────────────────────────────────────

function makeQC(gcTime = 0) {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime } },
  })
}

function Wrapper({ children, qc }: { children: React.ReactNode; qc: QueryClient }) {
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

beforeEach(() => {
  mockTranslateArticle.mockReset()
  mockToastError.mockReset()
  mockMarkAsRead.mockReset()
})

// ── AM1-AM14 tests will be added in Step 4 (after ArticleModal.tsx is modified) ──
// Placeholder to keep the file valid until then.

describe('ArticleModal', () => {
  it('placeholder — AM1-AM14 added after ArticleModal.tsx is modified', () => {
    expect(true).toBe(true)
  })
})
