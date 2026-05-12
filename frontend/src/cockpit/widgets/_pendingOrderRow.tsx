import { toast } from 'sonner'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
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
  updatePendingOrder,
  deletePendingOrder,
  type PendingOrder,
} from '../lib/api/cockpitPendingOrdersApi'
import { SetupTypeBadge } from '../components/SetupTypeBadge'

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt2(n: number | null): string {
  if (n == null) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDistance(pct: number | null): string {
  if (pct == null) return '—'
  const sign = pct >= 0 ? '+' : '-'
  return `${sign}${Math.abs(pct).toFixed(2)}%`
}

function distanceClass(pct: number | null): { className?: string; style?: React.CSSProperties } {
  if (pct == null) return {}
  const abs = Math.abs(pct)
  if (abs > 5) return { style: { color: 'var(--color-text-muted)' } }
  if (abs < 1) return { className: 'font-bold' }
  return {}
}

// ── table styles ──────────────────────────────────────────────────────────────

const tdBase: React.CSSProperties = {
  padding: '5px 4px',
  fontSize: 'var(--font-size-caption)',
  borderBottom: '1px solid var(--color-table-border)',
  verticalAlign: 'middle',
}

const btnStyle: React.CSSProperties = {
  padding: '1px 6px',
  height: '20px',
  fontSize: 'var(--font-size-caption)',
}

// ── PendingOrderRow ───────────────────────────────────────────────────────────

type SetupType = 'BREAKOUT' | 'PULLBACK' | 'RECLAIM' | 'EARNINGS_DRIFT' | 'EXTENDED' | 'BROKEN' | 'NONE' | null

type Props = {
  order: PendingOrder
  onEdit: (order: PendingOrder) => void
}

export function PendingOrderRow({ order, onEdit }: Props) {
  const queryClient = useQueryClient()

  const triggeredMutation = useMutation({
    mutationFn: () => updatePendingOrder(order.id, { status: 'TRIGGERED' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cockpit-pending-orders'] })
      toast('已标记为 TRIGGERED，可在 Positions widget 手工录入实际持仓')
    },
  })

  const cancelMutation = useMutation({
    mutationFn: () => updatePendingOrder(order.id, { status: 'CANCELLED' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['cockpit-pending-orders'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePendingOrder(order.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['cockpit-pending-orders'] }),
  })

  const dist = distanceClass(order.distanceToTriggerPct)

  return (
    <tr>
      <td style={{ ...tdBase, fontWeight: 'var(--font-weight-medium)' }}>{order.ticker}</td>
      <td style={tdBase}>
        <SetupTypeBadge value={order.setupType as SetupType} />
      </td>
      <td style={tdBase}>{fmt2(order.entryPrice)}</td>
      <td style={tdBase}>{fmt2(order.stopPrice)}</td>
      <td style={tdBase}>{fmt2(order.lastClose)}</td>
      <td
        data-testid={`dist-cell-${order.id}`}
        style={{ ...tdBase, ...(dist.style ?? {}) }}
        className={dist.className}
      >
        {formatDistance(order.distanceToTriggerPct)}
      </td>
      <td style={tdBase}>
        {order.riskPct != null ? `${order.riskPct.toFixed(1)}%` : '—'}
      </td>
      <td style={tdBase}>{order.expirationDate ?? '—'}</td>
      <td style={{ ...tdBase, whiteSpace: 'nowrap' }}>
        <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
          {order.status === 'ACTIVE' && (
            <>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    size="sm"
                    variant="outline"
                    style={btnStyle}
                    data-testid={`triggered-btn-${order.id}`}
                    disabled={triggeredMutation.isPending}
                  >
                    Triggered
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>确认标记为已触发</AlertDialogTitle>
                    <AlertDialogDescription>
                      已在券商手动下单？将把订单标记为 TRIGGERED（不会自动创建 Position）
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>取消</AlertDialogCancel>
                    <AlertDialogAction onClick={() => triggeredMutation.mutate()}>
                      确认
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>

              <Button
                size="sm"
                variant="outline"
                style={btnStyle}
                data-testid={`cancel-btn-${order.id}`}
                disabled={cancelMutation.isPending}
                onClick={() => cancelMutation.mutate()}
              >
                Cancel
              </Button>
            </>
          )}

          <Button
            size="sm"
            variant="outline"
            style={btnStyle}
            data-testid={`edit-btn-${order.id}`}
            onClick={() => onEdit(order)}
          >
            Edit
          </Button>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <button
                data-testid={`delete-btn-${order.id}`}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--color-text-muted)', fontSize: '10px', padding: '0 2px',
                }}
                aria-label={`Delete ${order.ticker}`}
              >
                ✕
              </button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>确认删除</AlertDialogTitle>
                <AlertDialogDescription>
                  确认删除 {order.ticker} 条件单？此操作不可恢复
                </AlertDialogDescription>
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
  )
}
