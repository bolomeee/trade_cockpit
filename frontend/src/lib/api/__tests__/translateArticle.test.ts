import { describe, it, expect, beforeEach } from 'vitest'

// ── Hoisted mock: intercept callAiTask before module loads ────────────────────
const { mockCallAiTask } = vi.hoisted(() => ({
  mockCallAiTask: vi.fn(),
}))

vi.mock('@/cockpit/lib/api/aiApi', () => ({
  callAiTask: mockCallAiTask,
}))

import { translateArticle } from '@/lib/api/translateArticle'

// ── Fixtures ──────────────────────────────────────────────────────────────────

const MOCK_RESPONSE = {
  memoId: 1,
  taskType: 'translate_article',
  schemaVersion: 'v1',
  output: { titleZh: '测试标题', contentZh: '测试正文' },
  meta: {
    modelUsed: 'deepseek-v3',
    tier: 'override',
    tokensIn: 50,
    tokensOut: 30,
    costUsd: 0.0001,
    latencyMs: 400,
    cacheHit: false,
  },
}

beforeEach(() => {
  mockCallAiTask.mockReset()
})

// ── LIB1 ─────────────────────────────────────────────────────────────────────

describe('LIB1: translateArticle forwards to callAiTask', () => {
  it('calls callAiTask("translate_article", input) and returns its result', async () => {
    mockCallAiTask.mockResolvedValue(MOCK_RESPONSE)

    const input = { title: 'Test Title', contentText: 'Some text content' }
    const result = await translateArticle(input)

    expect(mockCallAiTask).toHaveBeenCalledTimes(1)
    expect(mockCallAiTask).toHaveBeenCalledWith('translate_article', input)
    expect(result).toEqual(MOCK_RESPONSE)
  })

  it('passes optional targetLang through to callAiTask', async () => {
    mockCallAiTask.mockResolvedValue(MOCK_RESPONSE)

    const input = { title: 'T', contentText: 'C', targetLang: 'zh-CN' as const }
    await translateArticle(input)

    expect(mockCallAiTask).toHaveBeenCalledWith('translate_article', input)
  })
})
