import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Loader2, Upload, CircleX } from 'lucide-react'
import { toast } from 'sonner'

import { getSignals } from '@/lib/api/signals'
import { removeStock, updateColor } from '@/lib/api/watchlist'
import { useAppStore } from '@/store/useAppStore'
import { AddStockCard } from '@/components/features/dashboard/AddStockCard'
import { ColorTagButton } from '@/components/features/dashboard/ColorTagButton'
import { CsvImportDialog } from '@/components/features/dashboard/CsvImportDialog'
import { SignalBadge } from '@/components/features/dashboard/SignalBadge'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import type { LabelColor, SignalBoardItem, SignalType } from '@/types/signal'
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

function exportCsv(stocks: SignalBoardItem[]) {
  const rows = stocks.map(
    (s) => `${s.ticker},"${s.name.replace(/"/g, '""')}",${s.labelColor ?? 'none'}`,
  )
  const csv = ['ticker,name,color', ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `watchlist-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export function WatchlistWidget() {
  const setSelectedSymbol = useAppStore((s) => s.setSelectedSymbol)
  const queryClient = useQueryClient()
  const [importOpen, setImportOpen] = useState(false)

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

  const handleImportSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['signals'] })
    queryClient.invalidateQueries({ queryKey: ['watchlist'] })
  }

  return (
    <div className="flex h-full flex-col gap-1" style={{ marginTop: '-5px', marginLeft: '-5px' }}>
      <div className="flex items-center gap-1">
        <div className="min-w-0 flex-1">
          <AddStockCard />
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          title="批量导入 CSV"
          onClick={() => setImportOpen(true)}
        >
          <Upload size={14} />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          title="导出 CSV"
          disabled={sorted.length === 0}
          onClick={() => exportCsv(sorted)}
        >
          <Download size={14} />
        </Button>
      </div>
      <CsvImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onSuccess={handleImportSuccess}
      />
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
        <div className="flex-1 overflow-y-auto">
        <Table className="text-[11px] [&_th]:h-5 [&_th]:py-1 [&_th]:px-2 [&_th]:text-left [&_td]:py-[3px] [&_td]:px-2">
          <TableHeader className="sticky top-0 z-10 bg-card">
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
        </div>
      )}
    </div>
  )
}

function WatchlistRow({ stock, onSelect }: { stock: SignalBoardItem; onSelect: () => void }) {
  const { ticker, name, signalType, closePrice, distancePct, labelColor } = stock
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

  const colorMutation = useMutation({
    mutationFn: (color: LabelColor) => updateColor(ticker, color),
    onSuccess: invalidate,
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'NOT_FOUND') {
        invalidate()
        return
      }
      toast('颜色标记更新失败，请重试')
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
      <TableCell className="font-bold">
        <div className="flex items-center gap-1.5">
          <ColorTagButton
            ticker={ticker}
            color={labelColor}
            onChange={(color) => colorMutation.mutate(color)}
          />
          {ticker}
        </div>
      </TableCell>
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
              className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:text-destructive"
            >
              <CircleX size={14} strokeWidth={1.5} />
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
