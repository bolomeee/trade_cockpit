import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { getPendingOrders, type PendingOrderQueryStatus, type PendingOrder } from '../lib/api/cockpitPendingOrdersApi'
import { PendingOrderRow } from './_pendingOrderRow'
import { PendingOrderFormDialog } from '../dialogs/PendingOrderFormDialog'

const HEADERS = ['Ticker', 'Setup', 'Entry', 'Stop', 'Last', 'Dist', 'Risk%', 'Exp']

const thStyle: React.CSSProperties = {
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-text-secondary)',
  fontWeight: 'var(--font-weight-medium)',
  padding: '4px 4px',
  textAlign: 'left',
  borderBottom: '1px solid var(--color-border)',
  whiteSpace: 'nowrap',
}

const btnStyle: React.CSSProperties = { padding: '2px 8px', height: '24px', fontSize: 'var(--font-size-caption)' }

type FilterStatus = Extract<PendingOrderQueryStatus, 'active' | 'all'>

type FilterBtnProps = {
  label: string
  val: FilterStatus
  current: FilterStatus
  onSelect: (v: FilterStatus) => void
}

function FilterBtn({ label, val, current, onSelect }: FilterBtnProps) {
  return (
    <Button size="sm" variant={current === val ? 'default' : 'outline'} onClick={() => onSelect(val)} style={btnStyle}>
      {label}
    </Button>
  )
}

export function PendingOrdersWidget() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<FilterStatus>('active')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editOrder, setEditOrder] = useState<PendingOrder | null>(null)

  const query = useQuery({
    queryKey: ['cockpit-pending-orders', statusFilter],
    queryFn: () => getPendingOrders(statusFilter),
    staleTime: 30 * 1000,
    retry: false,
  })

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    padding: '10px',
    gap: '8px',
    overflow: 'auto',
    fontSize: 'var(--font-size-body)',
    color: 'var(--color-text-primary)',
  }

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontWeight: 'var(--font-weight-medium)' }}>Pending Orders</span>
        <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
          <FilterBtn label="Active" val="active" current={statusFilter} onSelect={setStatusFilter} />
          <FilterBtn label="All" val="all" current={statusFilter} onSelect={setStatusFilter} />
          <Button
            size="sm"
            onClick={() => setDialogOpen(true)}
            style={{ ...btnStyle, marginLeft: '4px' }}
          >
            + New Order
          </Button>
        </div>
      </div>

      {/* Body */}
      {query.isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} style={{ height: '28px', width: '100%' }} />
          ))}
        </div>
      ) : query.isError ? (
        <div
          data-testid="error-banner"
          style={{ color: 'var(--color-destructive)', fontSize: 'var(--font-size-caption)', padding: '8px 0' }}
        >
          加载失败，请稍后重试
        </div>
      ) : query.data?.length === 0 ? (
        <div
          data-testid="empty-state"
          style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-caption)', padding: '16px 0', textAlign: 'center' }}
        >
          暂无 pending order
        </div>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <thead>
            <tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {query.data?.map((order) => (
              <PendingOrderRow
                key={order.id}
                order={order}
                onEdit={(o) => setEditOrder(o)}
              />
            ))}
          </tbody>
        </table>
      )}

      {/* New Order Dialog */}
      {dialogOpen && (
        <PendingOrderFormDialog
          mode="new"
          open={dialogOpen}
          onSaved={() => {
            setDialogOpen(false)
            queryClient.invalidateQueries({ queryKey: ['cockpit-pending-orders'] })
          }}
          onClose={() => setDialogOpen(false)}
        />
      )}

      {/* Edit Order Dialog */}
      {editOrder && (
        <PendingOrderFormDialog
          mode="edit"
          open={!!editOrder}
          initialOrder={editOrder}
          onSaved={() => {
            setEditOrder(null)
            queryClient.invalidateQueries({ queryKey: ['cockpit-pending-orders'] })
          }}
          onClose={() => setEditOrder(null)}
        />
      )}
    </div>
  )
}
