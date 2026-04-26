import { apiFetch } from '@/lib/api/client'

export type PendingOrderStatus = 'ACTIVE' | 'TRIGGERED' | 'CANCELLED' | 'EXPIRED'
export type PendingOrderQueryStatus = 'active' | 'all' | 'triggered' | 'cancelled' | 'expired'

export type PendingOrder = {
  id: number
  ticker: string
  setupType: string | null
  entryPrice: number
  stopPrice: number
  shares: number
  target2r: number | null
  target3r: number | null
  expirationDate: string | null
  status: PendingOrderStatus
  lastClose: number | null
  distanceToTriggerPct: number | null
  riskPct: number | null
  notes: string | null
  createdAt: string
  updatedAt: string
}

export type PendingOrderInput = {
  ticker: string
  setupType?: string
  entryPrice: number
  stopPrice: number
  shares: number
  target2r?: number
  target3r?: number
  expirationDate?: string
  notes?: string
}

export type PendingOrderPatch = {
  ticker?: string
  setupType?: string
  entryPrice?: number
  stopPrice?: number
  shares?: number
  target2r?: number
  target3r?: number
  expirationDate?: string
  notes?: string
  status?: PendingOrderStatus
}

export function getPendingOrders(status: PendingOrderQueryStatus = 'active'): Promise<PendingOrder[]> {
  return apiFetch<PendingOrder[]>(`/cockpit/pending-orders?status=${status}`)
}

export function createPendingOrder(input: PendingOrderInput): Promise<PendingOrder> {
  return apiFetch<PendingOrder>('/cockpit/pending-orders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updatePendingOrder(id: number, patch: PendingOrderPatch): Promise<PendingOrder> {
  const body: Record<string, unknown> = {}
  if (patch.ticker !== undefined) body.ticker = patch.ticker
  if (patch.setupType !== undefined) body.setupType = patch.setupType
  if (patch.entryPrice !== undefined) body.entryPrice = patch.entryPrice
  if (patch.stopPrice !== undefined) body.stopPrice = patch.stopPrice
  if (patch.shares !== undefined) body.shares = patch.shares
  if (patch.target2r !== undefined) body.target2r = patch.target2r
  if (patch.target3r !== undefined) body.target3r = patch.target3r
  if (patch.expirationDate !== undefined) body.expirationDate = patch.expirationDate
  if (patch.notes !== undefined) body.notes = patch.notes
  if (patch.status !== undefined) body.status = patch.status
  return apiFetch<PendingOrder>(`/cockpit/pending-orders/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function deletePendingOrder(id: number): Promise<{ id: number; deleted: boolean }> {
  return apiFetch<{ id: number; deleted: boolean }>(`/cockpit/pending-orders/${id}`, {
    method: 'DELETE',
  })
}
