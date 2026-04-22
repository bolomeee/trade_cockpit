import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, X } from 'lucide-react'

import { getSignals } from '@/lib/api/signals'
import { removeStock } from '@/lib/api/watchlist'
import { useAppStore } from '@/store/useAppStore'
import { AddStockCard } from '@/components/features/dashboard/AddStockCard'
import { SignalBadge } from '@/components/features/dashboard/SignalBadge'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import type { SignalBoardItem, SignalType } from '@/types/signal'
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

const SIGNAL_PRIORITY: Record<SignalType, number> = {
  BREAKOUT: 0,
  BUY_ZONE: 1,
  NEUTRAL: 2,
  INSUFFICIENT: 3,
}

export function WatchlistWidget() {
  const setSelectedSymbol = useAppStore((s) => s.setSelectedSymbol)
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['signals'],
    queryFn: getSignals,
    staleTime: 30 * 1000,
  })

  const sorted = data
    ? [...data].sort(
        (a, b) => (SIGNAL_PRIORITY[a.signalType] ?? 3) - (SIGNAL_PRIORITY[b.signalType] ?? 3),
      )
    : []

  return (
    <div className="flex h-full flex-col gap-1" style={{ marginTop: '-5px', marginLeft: '-5px' }}>
      <AddStockCard />
      {isLoading && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} style={{ height: '40px' }} />
          ))}
        </div>
      )}
      {isError && <ErrorState onRetry={() => refetch()} />}
      {!isLoading && !isError && sorted.length === 0 && (
        <EmptyState title="还没有自选股，上方搜索添加一只吧" />
      )}
      {!isLoading && !isError && sorted.length > 0 && (
        <Table className="text-[11px] [&_th]:h-5 [&_th]:py-1 [&_th]:px-2 [&_th]:text-left [&_td]:py-[3px] [&_td]:px-2">
          <TableHeader>
            <TableRow>
              <TableHead className="w-14">Ticker</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Signal</TableHead>
              <TableHead>Close</TableHead>
              <TableHead>% MA150</TableHead>
              <TableHead className="w-6" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((stock) => (
              <WatchlistRow
                key={stock.ticker}
                stock={stock}
                onSelect={() => setSelectedSymbol(stock.ticker)}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

function WatchlistRow({ stock, onSelect }: { stock: SignalBoardItem; onSelect: () => void }) {
  const { ticker, name, signalType, closePrice, distancePct } = stock
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['signals'] })
    queryClient.invalidateQueries({ queryKey: ['watchlist'] })
  }

  const deleteMutation = useMutation({
    mutationFn: () => removeStock(ticker),
    onSuccess: () => {
      invalidate()
      setDialogOpen(false)
      setDeleteError(null)
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'NOT_FOUND') {
        invalidate()
        setDialogOpen(false)
        setDeleteError(null)
        return
      }
      setDeleteError('删除失败，请重试')
    },
  })

  const distanceColor =
    distancePct !== null
      ? distancePct >= 0
        ? 'var(--color-change-positive)'
        : 'var(--color-change-negative)'
      : 'var(--color-text-secondary)'

  return (
    <TableRow
      onClick={onSelect}
      className="cursor-pointer"
      style={{ opacity: deleteMutation.isPending ? 0.5 : 1 }}
    >
      <TableCell className="font-bold">{ticker}</TableCell>
      <TableCell className="text-muted-foreground">{name}</TableCell>
      <TableCell>
        <SignalBadge signalType={signalType} />
      </TableCell>
      <TableCell style={{ fontFamily: 'var(--font-family-numeric)' }}>
        {closePrice !== null ? `$${closePrice.toFixed(2)}` : '—'}
      </TableCell>
      <TableCell
        style={{ fontFamily: 'var(--font-family-numeric)', color: distanceColor }}
      >
        {distancePct !== null
          ? `${distancePct >= 0 ? '+' : ''}${distancePct.toFixed(1)}%`
          : '—'}
      </TableCell>
      <TableCell onClick={(e) => e.stopPropagation()}>
        <AlertDialog
          open={dialogOpen}
          onOpenChange={(open) => {
            setDialogOpen(open)
            if (!open) setDeleteError(null)
          }}
        >
          <AlertDialogTrigger asChild>
            <button
              type="button"
              aria-label={`删除 ${ticker}`}
              className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-destructive hover:text-destructive-foreground"
            >
              <X size={12} strokeWidth={2} />
            </button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>确认删除</AlertDialogTitle>
              <AlertDialogDescription>
                从 watchlist 中移除 <strong>{ticker}</strong>？
              </AlertDialogDescription>
            </AlertDialogHeader>
            {deleteError && (
              <div style={{ color: 'var(--color-error)', fontSize: 'var(--font-size-caption)' }}>
                {deleteError}
              </div>
            )}
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleteMutation.isPending}>取消</AlertDialogCancel>
              <AlertDialogAction
                variant="destructive"
                disabled={deleteMutation.isPending}
                onClick={(e) => {
                  e.preventDefault()
                  deleteMutation.mutate()
                }}
              >
                {deleteMutation.isPending ? (
                  <>
                    <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                    删除中…
                  </>
                ) : (
                  '删除'
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </TableCell>
    </TableRow>
  )
}
