import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteJournal, getJournal } from '@/lib/api/journal'
import { getWatchlist } from '@/lib/api/watchlist'
import type { JournalEntry, JournalFilter } from '@/types/journal'
import { JournalTable } from '@/components/features/journal/JournalTable'
import { JournalFilterCard } from '@/components/features/journal/JournalFilterCard'
import { JournalEntryDialog } from '@/components/features/journal/JournalEntryDialog'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'

type DialogState =
  | { open: false }
  | { open: true; mode: 'new'; entry: null }
  | { open: true; mode: 'edit'; entry: JournalEntry }

export function JournalWidget() {
  const qc = useQueryClient()
  const [filter, setFilter] = useState<JournalFilter>({})
  const [dialog, setDialog] = useState<DialogState>({ open: false })

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
    <div className="flex h-full flex-col gap-4">
      <header className="flex items-center justify-between gap-3">
        <JournalFilterCard
          filter={filter}
          onChange={setFilter}
          tickerOptions={tickerOptions}
        />
        <button
          type="button"
          onClick={() => setDialog({ open: true, mode: 'new', entry: null })}
          style={{
            padding: '8px 16px',
            borderRadius: 'var(--radius-button)',
            border: '1px solid var(--color-border)',
            background: 'var(--color-text-primary)',
            color: 'var(--color-text-on-dark)',
            fontSize: 'var(--font-size-body)',
            cursor: 'pointer',
            flexShrink: 0,
          }}
        >
          + New Entry
        </button>
      </header>

      {journalQuery.isLoading && (
        <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
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
        <div className="min-w-0 overflow-x-auto">
          <JournalTable
            entries={filteredEntries}
            onEdit={(entry) => setDialog({ open: true, mode: 'edit', entry })}
            onDelete={(id) => deleteMutation.mutate(id)}
          />
        </div>
      )}

      <JournalEntryDialog
        open={dialog.open}
        onOpenChange={(next) => {
          if (!next) setDialog({ open: false })
        }}
        mode={dialog.open ? dialog.mode : 'new'}
        entry={dialog.open && dialog.mode === 'edit' ? dialog.entry : null}
      />
    </div>
  )
}
