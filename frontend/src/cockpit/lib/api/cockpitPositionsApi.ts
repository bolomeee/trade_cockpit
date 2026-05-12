import { apiFetch } from '@/lib/api/client'

export type PositionStatus = 'OPEN' | 'CLOSED'
export type NextAction = 'hold' | 'raise_stop' | 'reduce' | 'exit'
export type PositionQueryStatus = 'open' | 'closed' | 'all'

export type Position = {
  id: number
  ticker: string
  entryPrice: number
  entryDate: string
  shares: number
  stopPrice: number
  target2r: number | null
  target3r: number | null
  setupType: string | null
  status: PositionStatus
  lastClose: number | null
  rMultiple: number | null
  unrealizedPl: number | null
  positionValue: number | null
  earningsDate: string | null
  daysUntilEarnings: number | null
  nextAction: NextAction
  closedAt: string | null
  closePrice: number | null
  notes: string | null
  createdAt: string
  updatedAt: string
}

export type PositionSummary = {
  openRiskPct: number
  totalExposurePct: number
  pendingRiskPct: number
  positionsCount: number
  pendingCount: number
}

export type GetPositionsResponse = {
  summary: PositionSummary
  items: Position[]
}

export type PositionInput = {
  ticker: string
  entryPrice: number
  entryDate: string
  shares: number
  stopPrice: number
  target2r?: number
  target3r?: number
  setupType?: string
  notes?: string
}

export type PositionPatch = {
  stopPrice?: number
  status?: PositionStatus
  closedAt?: string
  closePrice?: number
  notes?: string
}

export function getPositions(status: PositionQueryStatus = 'open'): Promise<GetPositionsResponse> {
  return apiFetch<GetPositionsResponse>(`/cockpit/positions?status=${status}`)
}

export function createPosition(input: PositionInput): Promise<Position> {
  return apiFetch<Position>('/cockpit/positions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updatePosition(id: number, patch: PositionPatch): Promise<Position> {
  const body: Record<string, unknown> = {}
  if (patch.stopPrice !== undefined) body.stopPrice = patch.stopPrice
  if (patch.status !== undefined) body.status = patch.status
  if (patch.closedAt !== undefined) body.closedAt = patch.closedAt
  if (patch.closePrice !== undefined) body.closePrice = patch.closePrice
  if (patch.notes !== undefined) body.notes = patch.notes
  return apiFetch<Position>(`/cockpit/positions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function deletePosition(id: number): Promise<{ id: number; deleted: boolean }> {
  return apiFetch<{ id: number; deleted: boolean }>(`/cockpit/positions/${id}`, {
    method: 'DELETE',
  })
}
