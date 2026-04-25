import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { TopNav } from '../TopNav'

// ── Mocks ──────────────────────────────────────────────────────────────────────

vi.mock('@/hooks/useRefreshStatus', () => ({
  useRefreshStatus: () => ({ lastRefreshedAt: null, isRefreshing: false, refresh: vi.fn() }),
}))

vi.mock('@/cockpit/useCockpitLayoutStore', () => ({
  useCockpitLayoutStore: () => ({ resetLayout: vi.fn() }),
}))

// ── helpers ────────────────────────────────────────────────────────────────────

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  // Mock user-settings GET so dialog doesn't show errors
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          data: {
            accountSize: 100000,
            maxExposurePct: 80,
            singleTradeRiskPct: 1.0,
            defaultRiskPerTradePct: 0.75,
            baseCurrency: 'USD',
            updatedAt: '2026-04-25T00:00:00Z',
          },
        }),
    }),
  )
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <TopNav />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

beforeEach(() => {
  vi.clearAllMocks()
})

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('S12 – gear button visibility by route', () => {
  it('renders ⚙ Settings button on /cockpit route', () => {
    renderAt('/cockpit')
    expect(screen.getByText('⚙ Settings')).toBeInTheDocument()
  })

  it('does NOT render ⚙ Settings on / route', () => {
    renderAt('/')
    expect(screen.queryByText('⚙ Settings')).not.toBeInTheDocument()
  })

  it('does NOT render ⚙ Settings on /journal route', () => {
    renderAt('/journal')
    expect(screen.queryByText('⚙ Settings')).not.toBeInTheDocument()
  })
})

describe('S13 – settings dialog open/close via TopNav', () => {
  it('clicking ⚙ Settings opens the dialog', async () => {
    renderAt('/cockpit')
    fireEvent.click(screen.getByText('⚙ Settings'))
    await waitFor(() => {
      expect(screen.getByText('User Settings')).toBeInTheDocument()
    })
  })

  it('clicking Cancel in dialog closes it', async () => {
    renderAt('/cockpit')
    fireEvent.click(screen.getByText('⚙ Settings'))
    await waitFor(() => screen.getByText('Cancel'))
    fireEvent.click(screen.getByText('Cancel'))
    await waitFor(() => {
      expect(screen.queryByText('User Settings')).not.toBeInTheDocument()
    })
  })
})
