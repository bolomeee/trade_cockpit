import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getUserSettings, updateUserSettings } from '../userSettingsApi'

const mockSettings = {
  accountSize: 100000,
  maxExposurePct: 80,
  singleTradeRiskPct: 1.0,
  defaultRiskPerTradePct: 0.75,
  baseCurrency: 'USD',
  updatedAt: '2026-04-25T10:00:00Z',
}

const okResponse = (data: unknown) => ({
  ok: true,
  json: () => Promise.resolve({ data }),
})

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse(mockSettings)))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('S1 – userSettingsApi.getUserSettings', () => {
  it('calls GET /api/cockpit/user-settings', async () => {
    await getUserSettings()
    expect(global.fetch).toHaveBeenCalledWith('/api/cockpit/user-settings', undefined)
  })

  it('returns camelCase fields matching API contract', async () => {
    const result = await getUserSettings()
    expect(result.accountSize).toBe(100000)
    expect(result.maxExposurePct).toBe(80)
    expect(result.singleTradeRiskPct).toBe(1.0)
    expect(result.defaultRiskPerTradePct).toBe(0.75)
    expect(result.baseCurrency).toBe('USD')
    expect(result.updatedAt).toBe('2026-04-25T10:00:00Z')
  })
})

describe('S2 – userSettingsApi.updateUserSettings', () => {
  it('calls PUT with only the provided patch fields', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse(mockSettings)))
    await updateUserSettings({ accountSize: 120000 })

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(call[0]).toBe('/api/cockpit/user-settings')
    const init = call[1] as RequestInit
    expect(init.method).toBe('PUT')
    expect(JSON.parse(init.body as string)).toEqual({ accountSize: 120000 })
  })

  it('partial patch does not include unmentioned fields', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse(mockSettings)))
    await updateUserSettings({ singleTradeRiskPct: 0.75 })

    const init = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit
    const body = JSON.parse(init.body as string)
    expect(body).toEqual({ singleTradeRiskPct: 0.75 })
    expect(body.accountSize).toBeUndefined()
  })
})
