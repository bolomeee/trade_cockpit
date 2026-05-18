import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { DecisionPanelWidget } from '../DecisionPanelWidget'
import { SetupTypeBadge } from '../../components/SetupTypeBadge'
import { useCockpitStore } from '@/store/cockpitStore'
import type { CapitulationEvidence } from '../../lib/api/cockpitDecisionApi'

// ── Fixtures ───────────────────────────────────────────────────────────────────

const mockEvidence: CapitulationEvidence = {
  volZscore: 2.71,
  drop5dPct: -12.4,
  reversalDay: true,
}

const baseDecision = {
  ticker: 'CRWD',
  setupType: 'CAPITULATION' as const,
  setupQuality: 'A' as const,
  entryPrice: 350,
  stopPrice: 330,
  target2r: 390,
  target3r: 410,
  rewardRisk: 2,
  riskPerShare: 20,
  suggestedShares: 50,
  positionValue: 17500,
  accountRiskPct: 1.0,
  effectiveRiskPct: 1.0,
  regimeCap: 1.0,
  userSettingCap: 1.0,
  earningsRisk: null,
  earningsDate: null,
  deterministicHash: 'cap123de456789',
  capitulationEvidence: mockEvidence,
}

function makeFetch(data: Record<string, unknown>) {
  return vi.fn((url: string) => {
    if (!url.includes('/cockpit/decision/')) {
      return Promise.reject(new Error(`Unexpected URL: ${url}`))
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ data }),
    })
  }) as unknown as typeof fetch
}

function renderWidget() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <DecisionPanelWidget />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  useCockpitStore.setState({ selectedTicker: null })
})

afterEach(() => {
  useCockpitStore.setState({ selectedTicker: null })
  vi.unstubAllGlobals()
})

// ── T1: CapitulationEvidence type is importable with camelCase fields ──────────

describe('T1 – CapitulationEvidence type importable with correct camelCase fields', () => {
  it('fields volZscore / drop5dPct / reversalDay exist with correct types', () => {
    const ev: CapitulationEvidence = { volZscore: 2.71, drop5dPct: -12.4, reversalDay: true }
    expect(ev.volZscore).toBe(2.71)
    expect(ev.drop5dPct).toBe(-12.4)
    expect(ev.reversalDay).toBe(true)
  })
})

// ── T2: CAPITULATION renders 3 chip rows ──────────────────────────────────────

describe('T2 – CAPITULATION renders Vol z-score / Drop 5d / Reversal day chips', () => {
  it('shows 3 chips with correct formatted values when evidence is present', async () => {
    vi.stubGlobal('fetch', makeFetch(baseDecision))
    useCockpitStore.setState({ selectedTicker: 'CRWD' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByText('Vol z-score')).toBeInTheDocument()
    })

    expect(screen.getByText('2.71')).toBeInTheDocument()
    expect(screen.getByText('Drop 5d')).toBeInTheDocument()
    expect(screen.getByText('-12.4%')).toBeInTheDocument()
    expect(screen.getByText('Reversal day')).toBeInTheDocument()
    expect(screen.getByText('是')).toBeInTheDocument()
  })
})

// ── T3: non-CAPITULATION setup does not render chips ─────────────────────────

describe('T3 – non-CAPITULATION setup: chips absent (even if evidence field present)', () => {
  it('setupType=BREAKOUT: no chip rows rendered', async () => {
    const data = { ...baseDecision, setupType: 'BREAKOUT' }
    vi.stubGlobal('fetch', makeFetch(data))
    useCockpitStore.setState({ selectedTicker: 'CRWD' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByText('350.00')).toBeInTheDocument()
    })

    expect(screen.queryByText('Vol z-score')).not.toBeInTheDocument()
    expect(screen.queryByText('Drop 5d')).not.toBeInTheDocument()
    expect(screen.queryByText('Reversal day')).not.toBeInTheDocument()
  })
})

// ── T4: CAPITULATION + capitulationEvidence=null → no chips ──────────────────

describe('T4 – CAPITULATION with capitulationEvidence=null: no chips rendered', () => {
  it('chips absent when evidence is null (backend anomaly defence)', async () => {
    const data = { ...baseDecision, capitulationEvidence: null }
    vi.stubGlobal('fetch', makeFetch(data))
    useCockpitStore.setState({ selectedTicker: 'CRWD' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByText('350.00')).toBeInTheDocument()
    })

    expect(screen.queryByText('Vol z-score')).not.toBeInTheDocument()
    expect(screen.queryByText('Drop 5d')).not.toBeInTheDocument()
    expect(screen.queryByText('Reversal day')).not.toBeInTheDocument()
  })
})

// ── T5: CAPITULATION reversalDay=false renders "否" ───────────────────────────

describe('T5 – CAPITULATION reversalDay=false: Reversal day chip shows "否"', () => {
  it('renders "否" for false branch; "是" absent', async () => {
    const data = {
      ...baseDecision,
      capitulationEvidence: { volZscore: 1.5, drop5dPct: -8.0, reversalDay: false },
    }
    vi.stubGlobal('fetch', makeFetch(data))
    useCockpitStore.setState({ selectedTicker: 'CRWD' })
    renderWidget()

    await waitFor(() => {
      expect(screen.getByText('否')).toBeInTheDocument()
    })

    expect(screen.queryByText('是')).not.toBeInTheDocument()
  })
})

// ── T6: SetupTypeBadge CAPITULATION + PULLBACK backward compat ────────────────

describe('T6 – SetupTypeBadge CAPITULATION and PULLBACK render correctly', () => {
  it('CAPITULATION renders CAP_REV label with var(--color-setup-capitulation)', () => {
    const { container } = render(<SetupTypeBadge value="CAPITULATION" />)
    const span = container.querySelector('span')!
    expect(span.textContent).toBe('CAP_REV')
    expect(span.style.color).toBe('var(--color-setup-capitulation)')
  })

  it('PULLBACK still renders with var(--color-setup-pullback) (backward compat)', () => {
    const { container } = render(<SetupTypeBadge value="PULLBACK" />)
    const span = container.querySelector('span')!
    expect(span.textContent).toBe('PULLBACK')
    expect(span.style.color).toBe('var(--color-setup-pullback)')
  })
})
