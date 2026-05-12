import { apiFetch } from '@/lib/api/client'

export type UserSettings = {
  accountSize: number
  maxExposurePct: number
  singleTradeRiskPct: number
  defaultRiskPerTradePct: number
  baseCurrency: string
  updatedAt: string
}

export function getUserSettings(): Promise<UserSettings> {
  return apiFetch<UserSettings>('/cockpit/user-settings')
}

export function updateUserSettings(
  patch: Partial<Omit<UserSettings, 'updatedAt'>>,
): Promise<UserSettings> {
  return apiFetch<UserSettings>('/cockpit/user-settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
}
