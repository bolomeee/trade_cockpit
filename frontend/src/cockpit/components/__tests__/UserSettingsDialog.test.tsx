import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { UserSettingsDialog } from '../UserSettingsDialog'

// ── Mock data ──────────────────────────────────────────────────────────────────

const mockSettings = {
  accountSize: 99999,   // intentionally different from component defaultValues (100000)
  maxExposurePct: 80,
  singleTradeRiskPct: 1.0,
  defaultRiskPerTradePct: 0.75,
  baseCurrency: 'USD',
  updatedAt: '2026-04-25T10:00:00Z',
}

function makeSettingsFetch(putResponse?: object) {
  return vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/cockpit/user-settings' && (!init || !init.method || init.method === 'GET')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: mockSettings }),
      })
    }
    if (url === '/api/cockpit/user-settings' && init?.method === 'PUT') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: putResponse ?? mockSettings }),
      })
    }
    return Promise.reject(new Error(`Unexpected: ${url} ${init?.method}`))
  }) as unknown as typeof fetch
}

function renderDialog(onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
  const result = render(
    <QueryClientProvider client={qc}>
      <UserSettingsDialog open onClose={onClose} />
    </QueryClientProvider>,
  )
  return { qc, invalidateSpy, onClose, ...result }
}

async function submitForm() {
  const user = userEvent.setup()
  await user.click(screen.getByText('Save Settings'))
}

// Waits until form.reset() has fired with data from the mocked GET response.
// Uses accountSize=99999 as sentinel (different from component defaultValues=100000).
async function waitForFormReset() {
  await waitFor(() => {
    expect((screen.getByLabelText('Account size') as HTMLInputElement).value).toBe('99999')
  })
}

// ── Setup / teardown ────────────────────────────────────────────────���─────────

beforeEach(() => {
  vi.stubGlobal('fetch', makeSettingsFetch())
})

afterEach(() => {
  vi.unstubAllGlobals()
})

// ── Tests ────────────────────────���─────────────────────────────────────────────

describe('S9 – mount → GET user-settings → form pre-filled', () => {
  it('calls GET exactly once on mount and fills form', async () => {
    renderDialog()
    await waitForFormReset()
    const getCalls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      (c) => c[0] === '/api/cockpit/user-settings' && (!c[1] || !c[1].method || c[1].method === 'GET'),
    )
    expect(getCalls.length).toBe(1)
  })

  it('form values match API response fields', async () => {
    renderDialog()
    await waitForFormReset()
    expect((screen.getByLabelText('Account size') as HTMLInputElement).value).toBe('99999')
    expect((screen.getByLabelText('Max exposure %') as HTMLInputElement).value).toBe('80')
    expect((screen.getByLabelText('Single-trade risk %') as HTMLInputElement).value).toBe('1')
    expect((screen.getByLabelText('Default risk per trade %') as HTMLInputElement).value).toBe('0.75')
  })
})

describe('S10 – zod validation errors', () => {
  it('accountSize=0 shows validation error', async () => {
    renderDialog()
    await waitForFormReset()

    fireEvent.change(screen.getByLabelText('Account size'), { target: { value: '0' } })
    await submitForm()

    await waitFor(() => {
      expect(screen.getByText('Account size must be > 0')).toBeInTheDocument()
    })
  })

  it('maxExposurePct=101 shows validation error', async () => {
    renderDialog()
    await waitForFormReset()

    fireEvent.change(screen.getByLabelText('Max exposure %'), { target: { value: '101' } })
    await submitForm()

    await waitFor(() => {
      expect(screen.getByText('Max 100')).toBeInTheDocument()
    })
  })

  it('singleTradeRiskPct=6 shows validation error', async () => {
    renderDialog()
    await waitForFormReset()

    fireEvent.change(screen.getByLabelText('Single-trade risk %'), { target: { value: '6' } })
    await submitForm()

    await waitFor(() => {
      expect(screen.getByText('Max 5')).toBeInTheDocument()
    })
  })
})

describe('S11 – submit dirty fields → PUT → invalidate queries', () => {
  it('PUT body contains only dirty fields; both query keys invalidated', async () => {
    // Use a distinct accountSize (98765) so we can detect when form.reset() has fired
    // (defaultValues use 100000, so input value '98765' only appears after the GET resolves)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            data: { ...mockSettings, accountSize: 98765 },
          }),
      }),
    )
    const { invalidateSpy, onClose } = renderDialog()

    // Wait until form.reset() fires (GET resolved + useEffect ran)
    await waitFor(() => {
      expect((screen.getByLabelText('Account size') as HTMLInputElement).value).toBe('98765')
    })

    // Change only accountSize (make it dirty: 98765 → 120000)
    const user = userEvent.setup()
    await user.clear(screen.getByLabelText('Account size'))
    await user.type(screen.getByLabelText('Account size'), '120000')
    await submitForm()

    // Verify PUT was called with only the dirty field
    await waitFor(() => {
      const putCalls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
        (c) => c[1]?.method === 'PUT',
      )
      expect(putCalls.length).toBe(1)
      const body = JSON.parse(putCalls[0][1].body as string)
      // Only the changed field (accountSize) should be in the patch
      expect(body.accountSize).toBe(120000)
      expect(body.maxExposurePct).toBeUndefined()
    })

    // Both query keys should be invalidated after success
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-user-settings'] }),
      )
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['cockpit-decision'] }),
      )
    })

    // Dialog closes on success
    expect(onClose).toHaveBeenCalled()
  })
})

describe('S13 – dialog open / close', () => {
  it('dialog is visible when open=true', () => {
    renderDialog()
    expect(screen.getByText('User Settings')).toBeInTheDocument()
  })

  it('Cancel button calls onClose', () => {
    const onClose = vi.fn()
    renderDialog(onClose)
    fireEvent.click(screen.getByText('Cancel'))
    expect(onClose).toHaveBeenCalled()
  })
})
