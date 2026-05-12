import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  outputDir: '../docs/验收/screenshots/F211',
  snapshotPathTemplate: '../docs/验收/screenshots/F211/{testFilePath}/{arg}{ext}',
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: '../docs/验收/playwright-report' }]],

  use: {
    baseURL: 'http://localhost:5173',
    channel: 'chrome',
    screenshot: 'on',
    video: 'off',
    trace: 'off',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },

  projects: [
    {
      name: 'smoke',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    },
  ],

  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 30_000,
  },
})
