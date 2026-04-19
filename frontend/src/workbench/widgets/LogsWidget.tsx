import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getLogs } from '@/lib/api/logs'
import type { LogLevelFilterValue } from '@/types/log'
import { LogLevelFilter } from '@/components/features/logs/LogLevelFilter'
import { LogsTable } from '@/components/features/logs/LogsTable'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'

export function LogsWidget() {
  const [filter, setFilter] = useState<LogLevelFilterValue>('ALL')

  const query = useQuery({
    queryKey: ['logs', filter],
    queryFn: () => getLogs(filter === 'ALL' ? undefined : { level: filter }),
    staleTime: 0,
  })

  return (
    <div className="flex h-full flex-col gap-4">
      <header className="flex items-center justify-end">
        <LogLevelFilter value={filter} onChange={setFilter} />
      </header>

      {query.isLoading && (
        <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} style={{ height: '48px', borderRadius: 'var(--radius-md)' }} />
          ))}
        </div>
      )}
      {query.isError && <ErrorState onRetry={() => query.refetch()} />}
      {query.isSuccess && query.data.length === 0 && (
        <EmptyState title="No logs match this filter" />
      )}
      {query.isSuccess && query.data.length > 0 && (
        <div className="min-w-0 overflow-x-auto">
          <LogsTable logs={query.data} />
        </div>
      )}
    </div>
  )
}
