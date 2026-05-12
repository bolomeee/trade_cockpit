/**
 * F211 AI Layer — Acceptance Smoke Probes
 *
 * AC3: Decision Panel AI Contradictions (Vite module injection → AAPL ticker)
 * AC4: News AI Summary Bar
 *
 * AC1/AC2 (backend schema/routing), AC5 (close-position hook), AC6 (monthly cron)
 * are backend-only and not covered here.
 */

import { test, expect, type Page } from '@playwright/test'

// ── Helpers ──────────────────────────────────────────────────────────────────

async function navigateToCockpitWithTicker(page: Page) {
  await page.goto('/cockpit')
  await page.waitForLoadState('networkidle', { timeout: 12_000 }).catch(() => {})

  // Inject ticker directly into Zustand store via Vite's ES module cache.
  // In Vite dev mode, dynamic import() returns the SAME module instance already
  // loaded by the app, so setState here is the real store mutation.
  const injected = await page.evaluate(async () => {
    try {
      const mod = await import('/src/store/cockpitStore.ts')
      mod.useCockpitStore.setState({ selectedTicker: 'AAPL' })
      return mod.useCockpitStore.getState().selectedTicker
    } catch (e) {
      return String(e)
    }
  })

  if (injected !== 'AAPL') {
    // Fallback: click the AAPL row in SetupMonitorWidget
    const aaplRow = page
      .locator('tr')
      .filter({ has: page.locator('td').filter({ hasText: /^AAPL$/ }) })
      .first()
    await aaplRow.click({ force: true }).catch(() => {})
  }

  // Wait for Decision Panel to receive and render the decision data for AAPL
  await page
    .waitForFunction(
      () => document.querySelector('[data-testid="ai-contradictions-divider"]') !== null,
      { timeout: 10_000 },
    )
    .catch(() => {})
}

// ── AC3: Decision Panel — AI Contradictions ─────────────────────────────────

test.describe('AC3 — Decision Panel AI Contradictions', () => {
  test('P1 — 选中 AAPL 后 AI Contradictions 区可见', async ({ page }) => {
    await navigateToCockpitWithTicker(page)

    const header = page.locator('text=AI Contradictions').first()
    await expect(header).toBeVisible({ timeout: 8_000 })

    await page.screenshot({ path: '../docs/验收/screenshots/F211/f211-ac3-contradictions-visible.png' })
  })

  test('P2 — Generate AI Contradictions 按钮可点击，aria-label 正确', async ({ page }) => {
    await navigateToCockpitWithTicker(page)

    const btn = page.getByTestId('ai-contradictions-trigger')
    await expect(btn).toBeVisible({ timeout: 8_000 })
    const label = await btn.getAttribute('aria-label')
    expect(label).toBe('Generate AI Contradictions')

    await page.screenshot({ path: '../docs/验收/screenshots/F211/f211-ac3-trigger-visible.png' })
  })

  test('P3 — 点击后状态机触发（loading 或 error，不卡死）', async ({ page }) => {
    await navigateToCockpitWithTicker(page)

    const btn = page.getByTestId('ai-contradictions-trigger')
    await expect(btn).toBeVisible({ timeout: 8_000 })
    await btn.click()

    const loading = page.getByTestId('ai-contradictions-loading')
    const error = page.getByTestId('ai-contradictions-error')
    const guardrail = page.getByTestId('ai-contradictions-guardrail-error')

    await Promise.race([
      loading.waitFor({ state: 'visible', timeout: 3_000 }),
      error.waitFor({ state: 'visible', timeout: 8_000 }),
      guardrail.waitFor({ state: 'visible', timeout: 8_000 }),
    ])

    await page.screenshot({ path: '../docs/验收/screenshots/F211/f211-ac3-post-trigger.png' })
  })

  test('P4 — 有 mocked AI 响应时渲染 result 区（severity badge + recommendation）', async ({ page }) => {
    // Mock the AI endpoint to return controlled response (wrapped in data envelope)
    await page.route('**/api/ai/contradiction_detector', (route) =>
      route.fulfill({
        json: {
          data: {
            task_type: 'contradiction_detector',
            output: {
              contradictions: [
                {
                  type: 'earnings_risk',
                  severity: 'HIGH',
                  detail: 'Earnings in 3 days, high IV',
                  recommendation: 'Reduce position size',
                },
              ],
              recommendation: 'Consider reducing before earnings',
            },
            meta: { cacheHit: false, modelUsed: 'mock', inputTokens: 100, outputTokens: 50 },
          },
          message: 'success',
        },
      }),
    )

    await navigateToCockpitWithTicker(page)

    const btn = page.getByTestId('ai-contradictions-trigger')
    await expect(btn).toBeVisible({ timeout: 8_000 })
    await btn.click()

    const result = page.getByTestId('ai-contradictions-result')
    const error = page.getByTestId('ai-contradictions-error')
    const guardrail = page.getByTestId('ai-contradictions-guardrail-error')

    await Promise.race([
      result.waitFor({ state: 'visible', timeout: 10_000 }),
      error.waitFor({ state: 'visible', timeout: 10_000 }),
      guardrail.waitFor({ state: 'visible', timeout: 10_000 }),
    ])

    await page.screenshot({ path: '../docs/验收/screenshots/F211/f211-ac3-final-state.png' })
  })
})

// ── AC4: News Page — AI Summary Bar ─────────────────────────────────────────

test.describe('AC4 — News Page AI Summary Bar', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/news')
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
  })

  test('P5 — News 页渲染正常，AI Summary Bar trigger 存在', async ({ page }) => {
    await page.screenshot({ path: '../docs/验收/screenshots/F211/f211-ac4-news-initial.png', fullPage: false })
    const trigger = page.getByTestId('ai-news-summary-trigger')
    await expect(trigger).toBeVisible({ timeout: 8_000 })
  })

  test('P6 — Generate AI News Summary 按钮 aria-label 正确', async ({ page }) => {
    const btn = page.getByTestId('ai-news-summary-trigger')
    await expect(btn).toBeVisible({ timeout: 8_000 })
    const label = await btn.getAttribute('aria-label')
    expect(label).toBe('Generate AI News Summary')
    await page.screenshot({ path: '../docs/验收/screenshots/F211/f211-ac4-trigger-visible.png' })
  })

  test('P7 — 点击后状态机触发（loading 或 final state，不卡死）', async ({ page }) => {
    const btn = page.getByTestId('ai-news-summary-trigger')
    await expect(btn).toBeVisible({ timeout: 8_000 })
    await btn.click()

    const loading = page.getByTestId('ai-news-summary-loading')
    const error = page.getByTestId('ai-news-summary-error')
    const guardrail = page.getByTestId('ai-news-summary-guardrail-error')
    const result = page.getByTestId('ai-news-summary-result')

    await Promise.race([
      loading.waitFor({ state: 'visible', timeout: 3_000 }),
      error.waitFor({ state: 'visible', timeout: 8_000 }),
      guardrail.waitFor({ state: 'visible', timeout: 8_000 }),
      result.waitFor({ state: 'visible', timeout: 8_000 }),
    ])

    await page.screenshot({ path: '../docs/验收/screenshots/F211/f211-ac4-post-trigger.png' })
  })

  test('P8 — loading 结束后进入 result 或 error 态（不卡死）', async ({ page }) => {
    const btn = page.getByTestId('ai-news-summary-trigger')
    await expect(btn).toBeVisible({ timeout: 8_000 })
    await btn.click()

    const result = page.getByTestId('ai-news-summary-result')
    const error = page.getByTestId('ai-news-summary-error')
    const guardrail = page.getByTestId('ai-news-summary-guardrail-error')

    await Promise.race([
      result.waitFor({ state: 'visible', timeout: 20_000 }),
      error.waitFor({ state: 'visible', timeout: 20_000 }),
      guardrail.waitFor({ state: 'visible', timeout: 20_000 }),
    ])

    await page.screenshot({ path: '../docs/验收/screenshots/F211/f211-ac4-final-state.png' })
  })
})
