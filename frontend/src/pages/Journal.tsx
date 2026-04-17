import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteJournal, getJournal } from '@/lib/api/journal'
import { getWatchlist } from '@/lib/api/watchlist'
import type { JournalFilter } from '@/types/journal'
import { JournalTable } from '@/components/features/journal/JournalTable'
import { JournalFilterCard } from '@/components/features/journal/JournalFilterCard'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'

export default function Journal() {
  const qc = useQueryClient()
  const [filter, setFilter] = useState<JournalFilter>({})

  const journalQuery = useQuery({
    queryKey: ['journal'],
    queryFn: () => getJournal(),
    staleTime: 0,
  })

  const watchlistQuery = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    staleTime: 30 * 1000,
  })

  const tickerOptions = useMemo(() => {
    const set = new Set((watchlistQuery.data ?? []).map((w) => w.ticker))
    return Array.from(set).sort()
  }, [watchlistQuery.data])

  const filteredEntries = useMemo(() => {
    const all = journalQuery.data?.items ?? []
    return all.filter((e) => {
      if (filter.ticker && e.ticker !== filter.ticker) return false
      if (filter.action && e.action !== filter.action) return false
      return true
    })
  }, [journalQuery.data, filter])

  const deleteMutation = useMutation({
    mutationFn: deleteJournal,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['journal'] }),
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
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1
          style={{
            fontSize: 'var(--font-size-hero)',
            fontWeight: 'var(--font-weight-bold)',
            color: 'var(--color-text-primary)',
            margin: 0,
          }}
        >
          Trade Journal
        </h1>
        <button
          type="button"
          disabled
          title="Coming in F007-c"
          style={{
            padding: '8px 16px',
            borderRadius: 'var(--radius-button)',
            border: '1px solid var(--color-border)',
            background: 'var(--color-text-primary)',
            color: 'var(--color-text-on-dark)',
            fontSize: 'var(--font-size-body)',
            cursor: 'not-allowed',
            opacity: 0.5,
          }}
        >
          + New Entry
        </button>
      </header>

      <JournalFilterCard
        filter={filter}
        onChange={setFilter}
        tickerOptions={tickerOptions}
      />

      {journalQuery.isLoading && (
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

      {journalQuery.isError && <ErrorState onRetry={() => journalQuery.refetch()} />}

      {journalQuery.isSuccess && filteredEntries.length === 0 && (
        <EmptyState title="还没有交易记录" description="点右上角 + New Entry 开始记录" />
      )}

      {journalQuery.isSuccess && filteredEntries.length > 0 && (
        <JournalTable
          entries={filteredEntries}
          onDelete={(id) => deleteMutation.mutate(id)}
        />
      )}
    </div>
  )
}
