import { apiFetch } from './client'
import type { JournalFilter, JournalListResponse } from '@/types/journal'

export function getJournal(filter?: JournalFilter): Promise<JournalListResponse> {
  const params = new URLSearchParams()
  if (filter?.ticker) params.set('ticker', filter.ticker)
  if (filter?.action) params.set('action', filter.action)
  // MVP: one-shot full list; backend cap 200
  params.set('limit', '200')
  const qs = params.toString()
  return apiFetch<JournalListResponse>(`/journal${qs ? `?${qs}` : ''}`)
}

export function deleteJournal(id: number): Promise<{ id: number; deleted: boolean }> {
  return apiFetch<{ id: number; deleted: boolean }>(`/journal/${id}`, {
    method: 'DELETE',
  })
}
