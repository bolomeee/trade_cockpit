import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getLogs } from '@/lib/api/logs'
import type { LogLevelFilterValue } from '@/types/log'
import { LogLevelFilter } from '@/components/features/logs/LogLevelFilter'
import { LogsTable } from '@/components/features/logs/LogsTable'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'

export default function Logs() {
  const [filter, setFilter] = useState<LogLevelFilterValue>('ALL')

  const query = useQuery({
    queryKey: ['logs', filter],
    queryFn: () => getLogs(filter === 'ALL' ? undefined : { level: filter }),
    staleTime: 0,
  })

  return (
    <div
      style={{
        maxWidth: '1053px',
        marginInline: 'auto',
        padding: 'var(--spacing-8) var(--spacing-6)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--spacing-6)',
      }}
    >
      <header style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
        <LogLevelFilter value={filter} onChange={setFilter} />
      </header>

      {query.isLoading && (
        <div
          style={{
            background: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-card)',
            padding: 'var(--spacing-4)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} style={{ height: '48px', borderRadius: 'var(--radius-md)' }} />
          ))}
        </div>
      )}

      {query.isError && <ErrorState onRetry={() => query.refetch()} />}

      {query.isSuccess && query.data.length === 0 && (
        <EmptyState title="No logs match this filter" />
      )}

      {query.isSuccess && query.data.length > 0 && <LogsTable logs={query.data} />}
    </div>
  )
}
