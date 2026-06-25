import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useRefreshHealth } from '@/hooks/useRefreshHealth'
import { TopNav } from '../TopNav'

// F221 / D108: TopNav refresh-health alert badge.

vi.mock('@/hooks/useRefreshStatus', () => ({
  useRefreshStatus: () => ({ lastRefreshedAt: null, isRefreshing: false, refresh: vi.fn() }),
}))
vi.mock('@/hooks/useRefreshHealth', () => ({
  useRefreshHealth: vi.fn(),
}))
vi.mock('@/cockpit/useCockpitLayoutStore', () => ({
  useCockpitLayoutStore: () => ({ resetLayout: vi.fn() }),
}))
vi.mock('@/hooks/useNewsArticles', () => ({
  useNewsArticles: () => ({ data: [] }),
}))

function renderTopNav() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <TooltipProvider>
        <MemoryRouter initialEntries={['/']}>
          <TopNav />
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  )
}

describe('F221 – TopNav refresh-health badge', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the alert badge when a refresh job is stale', () => {
    vi.mocked(useRefreshHealth).mockReturnValue({
      hasIssue: true,
      reasons: ['Universe 数据陈旧（56 天未刷新）'],
      recentErrors: 0,
      data: undefined,
    })
    renderTopNav()
    expect(screen.getByRole('button', { name: '刷新告警' })).toBeInTheDocument()
  })

  it('hides the badge when refresh health is OK', () => {
    vi.mocked(useRefreshHealth).mockReturnValue({
      hasIssue: false,
      reasons: [],
      recentErrors: 0,
      data: undefined,
    })
    renderTopNav()
    expect(screen.queryByRole('button', { name: '刷新告警' })).not.toBeInTheDocument()
  })
})
