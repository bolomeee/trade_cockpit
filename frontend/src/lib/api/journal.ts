import { apiFetch } from './client'
import type { JournalEntry, JournalFilter, JournalListResponse } from '@/types/journal'

export interface JournalEntryPayload {
  ticker: string
  action: string
  price: number
  date: string
  positionSize: number | null
  stopLoss: number | null
  targetPrice: number | null
  reason: string | null
  reference: string | null
}

export function getJournal(filter?: JournalFilter): Promise<JournalListResponse> {
  const params = new URLSearchParams()
  if (filter?.ticker) params.set('ticker', filter.ticker)
  if (filter?.action) params.set('action', filter.action)
  params.set('limit', '200')
  const qs = params.toString()
  return apiFetch<JournalListResponse>(`/journal${qs ? `?${qs}` : ''}`)
}

export function createJournal(payload: JournalEntryPayload): Promise<JournalEntry> {
  return apiFetch<JournalEntry>('/journal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateJournal(id: number, payload: JournalEntryPayload): Promise<JournalEntry> {
  return apiFetch<JournalEntry>(`/journal/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteJournal(id: number): Promise<{ id: number; deleted: boolean }> {
  return apiFetch<{ id: number; deleted: boolean }>(`/journal/${id}`, {
    method: 'DELETE',
  })
}
