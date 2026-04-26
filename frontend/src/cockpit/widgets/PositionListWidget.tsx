import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { getPositions, type PositionQueryStatus } from '../lib/api/cockpitPositionsApi'
import { RiskSummaryBar, PositionRow } from './_positionListRow'
import { PositionFormDialog } from '../dialogs/PositionFormDialog'

const HEADERS = ['Ticker', 'Entry', 'Last', 'Stop', 'R', 'P/L', 'Earn', 'Next']

const thStyle: React.CSSProperties = {
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-text-secondary)',
  fontWeight: 'var(--font-weight-medium)',
  padding: '4px 4px',
  textAlign: 'left',
  borderBottom: '1px solid var(--color-border)',
  whiteSpace: 'nowrap',
}

export function PositionListWidget() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<PositionQueryStatus>('open')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)

  const query = useQuery({
    queryKey: ['cockpit-positions', statusFilter],
    queryFn: () => getPositions(statusFilter),
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

  const FilterBtn = ({ label, val }: { label: string; val: PositionQueryStatus }) => (
    <Button
      size="sm"
      variant={statusFilter === val ? 'default' : 'outline'}
      onClick={() => { setStatusFilter(val); setExpandedId(null) }}
      style={{ padding: '2px 8px', height: '24px', fontSize: 'var(--font-size-caption)' }}
    >
      {label}
    </Button>
  )

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontWeight: 'var(--font-weight-medium)' }}>Positions</span>
        <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
          <FilterBtn label="Open" val="open" />
          <FilterBtn label="Closed" val="closed" />
          <FilterBtn label="All" val="all" />
          <Button
            size="sm"
            onClick={() => setDialogOpen(true)}
            style={{ padding: '2px 8px', height: '24px', fontSize: 'var(--font-size-caption)', marginLeft: '4px' }}
          >
            + New Position
          </Button>
        </div>
      </div>

      {/* Summary bar */}
      {query.data && <RiskSummaryBar s={query.data.summary} />}

      {/* Body */}
      {query.isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} style={{ height: '28px', width: '100%' }} />
          ))}
        </div>
      ) : query.isError ? (
        <div data-testid="error-banner"
          style={{ color: 'var(--color-destructive)', fontSize: 'var(--font-size-caption)', padding: '8px 0' }}>
          加载失败，请稍后重试
        </div>
      ) : query.data?.items.length === 0 ? (
        <div data-testid="empty-state"
          style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-caption)', padding: '16px 0', textAlign: 'center' }}>
          暂无持仓
        </div>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <thead>
            <tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {query.data?.items.map((p) => (
              <PositionRow
                key={p.id}
                position={p}
                expanded={expandedId === p.id}
                onToggle={() => setExpandedId((prev) => (prev === p.id ? null : p.id))}
              />
            ))}
          </tbody>
        </table>
      )}

      {/* New Position Dialog */}
      {dialogOpen && (
        <PositionFormDialog
          mode="new"
          open={dialogOpen}
          onSaved={() => {
            setDialogOpen(false)
            queryClient.invalidateQueries({ queryKey: ['cockpit-positions'] })
          }}
          onClose={() => setDialogOpen(false)}
        />
      )}
    </div>
  )
}
