import { apiFetch } from './client'
import type { SignalBoardItem } from '@/types/signal'

export function getSignals(): Promise<SignalBoardItem[]> {
  return apiFetch<SignalBoardItem[]>('/signals')
}
