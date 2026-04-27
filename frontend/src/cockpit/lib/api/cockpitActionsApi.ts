import { apiFetch } from '@/lib/api/client'

export type ActionType =
  | 'raise_stop'
  | 'cancel_order'
  | 'reduce_before_earnings'
  | 'tighten_stop'
  | 'approaching_trigger'
  | 'stable_position'

export type ActionItem = {
  ticker: string
  actionType: ActionType
  rationale: string
  refs: Record<string, unknown>
}

export type TodayActionsPayload = {
  asOfDate: string
  mustAct: ActionItem[]
  monitor: ActionItem[]
  noAction: ActionItem[]
}

export function getTodayActions(): Promise<TodayActionsPayload> {
  return apiFetch<TodayActionsPayload>('/cockpit/actions/today')
}
