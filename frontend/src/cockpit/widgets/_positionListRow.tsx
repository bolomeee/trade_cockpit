import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import {
  updatePosition,
  deletePosition,
  type Position,
  type PositionSummary,
  type PositionStatus,
} from '../lib/api/cockpitPositionsApi'
import { EarningsRiskDot } from '../components/EarningsRiskDot'

// ── helpers & constants ───────────────────────────────────────────────────────

export function fmt2(n: number | null): string {
  if (n == null) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function fmtPl(n: number | null): string {
  if (n == null) return '—'
  const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
  return n >= 0 ? `+$${abs}` : `-$${abs}`
}

type EarningsRiskValue = 'SAFE' | 'CAUTION' | 'DANGER' | null

export function deriveEarningsRisk(days: number | null): EarningsRiskValue {
  if (days == null || days <= 0) return null
  if (days <= 7) return 'DANGER'
  if (days <= 14) return 'CAUTION'
  return 'SAFE'
}

export const NEXT_ACTION_LABEL: Record<string, string> = {
  hold: 'Watch', raise_stop: 'Add', reduce: 'Reduce', exit: 'Sell',
}

export const NEXT_ACTION_COLOR: Record<string, string> = {
  hold: 'var(--color-action-watch)',
  raise_stop: 'var(--color-action-add)',
  reduce: 'var(--color-action-reduce)',
  exit: 'var(--color-action-sell)',
}

// ── RiskSummaryBar ────────────────────────────────────────────────────────────

export function RiskSummaryBar({ s }: { s: PositionSummary }) {
  return (
    <div
      data-testid="risk-summary-bar"
      style={{
        display: 'flex', gap: '12px', flexWrap: 'wrap',
        fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)',
        padding: '4px 0', borderBottom: '1px solid var(--color-border)',
      }}
    >
      <span>{`Open Risk: ${s.openRiskPct.toFixed(1)}%`}</span>
      <span>{`Exposure: ${s.totalExposurePct.toFixed(0)}%`}</span>
      <span>{`Pending: ${s.pendingRiskPct.toFixed(1)}%`}</span>
      <span>{`${s.positionsCount} pos`}</span>
      <span>{`${s.pendingCount} ord`}</span>
    </div>
  )
}

// ── InlineEditRow ─────────────────────────────────────────────────────────────

type InlineEditState = {
  stopPrice: string
  status: PositionStatus
  closedAt: string
  closePrice: string
  notes: string
}

const capStyle: React.CSSProperties = { fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }
const fieldStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: '2px' }
const inputStyle: React.CSSProperties = { height: '28px' }

function LabeledInput({
  id, label, type = 'text', value, width = 90, onChange,
}: {
  id: string; label: string; type?: string; value: string; width?: number; onChange: (v: string) => void
}) {
  return (
    <div style={fieldStyle}>
      <label htmlFor={id} style={capStyle}>{label}</label>
      <Input id={id} type={type} step="any" style={{ ...inputStyle, width }} value={value}
        onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

export function InlineEditRow({
  position, onSave, onCancel, isSaving,
}: {
  position: Position; onSave: (p: InlineEditState) => void; onCancel: () => void; isSaving: boolean
}) {
  const id = position.id
  const [state, setState] = useState<InlineEditState>({
    stopPrice: String(position.stopPrice),
    status: position.status,
    closedAt: position.closedAt ?? '',
    closePrice: position.closePrice != null ? String(position.closePrice) : '',
    notes: position.notes ?? '',
  })
  const set = (k: keyof InlineEditState) => (v: string) => setState((s) => ({ ...s, [k]: v }))

  return (
    <tr>
      <td colSpan={8} style={{ padding: '8px', backgroundColor: 'var(--color-table-row-alt)' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <LabeledInput id={`stop-${id}`} label="Stop price" type="number" value={state.stopPrice} onChange={set('stopPrice')} />
          <div style={fieldStyle}>
            <label htmlFor={`status-${id}`} style={capStyle}>Status</label>
            <select id={`status-${id}`} value={state.status}
              onChange={(e) => setState((s) => ({ ...s, status: e.target.value as PositionStatus }))}
              style={{ height: '28px', fontSize: 'var(--font-size-caption)', borderRadius: '4px', border: '1px solid var(--color-border)' }}>
              <option value="OPEN">OPEN</option>
              <option value="CLOSED">CLOSED</option>
            </select>
          </div>
          {state.status === 'CLOSED' && (
            <>
              <LabeledInput id={`closedat-${id}`} label="Closed at" type="datetime-local" value={state.closedAt} width={160} onChange={set('closedAt')} />
              <LabeledInput id={`closeprice-${id}`} label="Close price" type="number" value={state.closePrice} onChange={set('closePrice')} />
            </>
          )}
          <LabeledInput id={`notes-${id}`} label="Notes" value={state.notes} width={160} onChange={set('notes')} />
          <Button size="sm" disabled={isSaving} onClick={() => onSave(state)} style={{ marginTop: 'auto' }}>
            {isSaving ? 'Saving…' : 'Save'}
          </Button>
          <Button size="sm" variant="outline" onClick={onCancel} style={{ marginTop: 'auto' }}>Cancel</Button>
        </div>
      </td>
    </tr>
  )
}

// ── PositionRow ───────────────────────────────────────────────────────────────

const tdBase: React.CSSProperties = {
  padding: '6px 4px', fontSize: 'var(--font-size-caption)',
  borderBottom: '1px solid var(--color-table-border)', cursor: 'pointer', verticalAlign: 'top',
}

export function PositionRow({
  position, expanded, onToggle,
}: {
  position: Position; expanded: boolean; onToggle: () => void
}) {
  const queryClient = useQueryClient()

  const patchMutation = useMutation({
    mutationFn: (patch: InlineEditState) =>
      updatePosition(position.id, {
        stopPrice: patch.stopPrice ? Number(patch.stopPrice) : undefined,
        status: patch.status,
        closedAt: patch.closedAt || undefined,
        closePrice: patch.closePrice ? Number(patch.closePrice) : undefined,
        notes: patch.notes || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cockpit-positions'] })
      onToggle()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePosition(position.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['cockpit-positions'] }),
  })

  const rColor = (position.rMultiple ?? 0) >= 0 ? 'var(--color-change-positive)' : 'var(--color-change-negative)'
  const plColor = (position.unrealizedPl ?? 0) >= 0 ? 'var(--color-change-positive)' : 'var(--color-change-negative)'
  const earningsRisk = deriveEarningsRisk(position.daysUntilEarnings)
  const actionColor = NEXT_ACTION_COLOR[position.nextAction] ?? 'var(--color-text-muted)'

  return (
    <>
      <tr onClick={onToggle} style={{ backgroundColor: expanded ? 'var(--color-table-row-alt)' : undefined }}>
        <td style={{ ...tdBase, fontWeight: 'var(--font-weight-medium)' }}>
          {position.ticker}
          <div style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-muted)' }}>({position.shares} sh)</div>
        </td>
        <td style={tdBase}>{fmt2(position.entryPrice)}</td>
        <td style={tdBase}>{fmt2(position.lastClose)}</td>
        <td style={tdBase}>{fmt2(position.stopPrice)}</td>
        <td style={{ ...tdBase, color: rColor }}>{fmt2(position.rMultiple)}</td>
        <td style={{ ...tdBase, color: plColor }}>{fmtPl(position.unrealizedPl)}</td>
        <td style={tdBase}>
          {position.daysUntilEarnings != null && position.daysUntilEarnings > 0
            ? <EarningsRiskDot value={earningsRisk} daysUntil={position.daysUntilEarnings} />
            : '—'}
        </td>
        <td style={tdBase}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '4px' }}>
            <span data-testid={`next-action-chip-${position.id}`}
              style={{ color: actionColor, fontWeight: 'var(--font-weight-medium)', fontSize: 'var(--font-size-caption)' }}>
              {NEXT_ACTION_LABEL[position.nextAction] ?? position.nextAction}
            </span>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <button data-testid={`delete-btn-${position.id}`} onClick={(e) => e.stopPropagation()}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', fontSize: '10px', padding: '0 2px' }}
                  aria-label={`Delete ${position.ticker}`}>
                  ✕
                </button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>确认删除</AlertDialogTitle>
                  <AlertDialogDescription>确认删除 {position.ticker} 持仓？此操作不可恢复</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction onClick={() => deleteMutation.mutate()}>删除</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </td>
      </tr>
      {expanded && (
        <InlineEditRow position={position} onSave={(p) => patchMutation.mutate(p)}
          onCancel={onToggle} isSaving={patchMutation.isPending} />
      )}
    </>
  )
}
