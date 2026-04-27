import { useQuery } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { useCockpitStore } from '@/store/cockpitStore'
import { getTodayActions } from '../lib/api/cockpitActionsApi'
import { ActionListSection } from './_actionListSection'

export function ActionListWidget() {
  const setSelectedTicker = useCockpitStore((s) => s.setSelectedTicker)

  const query = useQuery({
    queryKey: ['cockpit-actions-today'],
    queryFn: getTodayActions,
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 'var(--font-weight-medium)' }}>Today&apos;s Actions</span>
        {query.data?.asOfDate && (
          <span
            data-testid="action-as-of-date"
            style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-muted)' }}
          >
            {query.data.asOfDate}
          </span>
        )}
      </div>

      {/* Body */}
      {query.isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} style={{ height: '40px', width: '100%' }} />
          ))}
        </div>
      ) : query.isError ? (
        <div
          data-testid="error-banner"
          style={{ color: 'var(--color-destructive)', fontSize: 'var(--font-size-caption)', padding: '8px 0' }}
        >
          加载失败，请稍后重试
        </div>
      ) : query.data &&
        query.data.mustAct.length === 0 &&
        query.data.monitor.length === 0 &&
        query.data.noAction.length === 0 ? (
        <div
          data-testid="empty-state"
          style={{
            color: 'var(--color-text-muted)',
            fontSize: 'var(--font-size-caption)',
            padding: '16px 0',
            textAlign: 'center',
          }}
        >
          暂无今日动作
        </div>
      ) : query.data ? (
        <>
          <ActionListSection variant="must" items={query.data.mustAct} onTickerClick={setSelectedTicker} />
          <ActionListSection variant="monitor" items={query.data.monitor} onTickerClick={setSelectedTicker} />
          <ActionListSection variant="noaction" items={query.data.noAction} onTickerClick={setSelectedTicker} />
          {/* AI Daily Brief 挂载点 — F209/F211 v2.0 */}
        </>
      ) : null}
    </div>
  )
}
