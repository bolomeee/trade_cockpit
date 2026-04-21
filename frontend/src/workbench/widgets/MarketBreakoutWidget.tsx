import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Loader2, Plus } from 'lucide-react'

import { getBreakouts } from '@/lib/api/market'
import { addStock } from '@/lib/api/watchlist'
import { ApiError } from '@/lib/api/client'
import { useAppStore } from '@/store/useAppStore'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { BreakoutItem } from '@/types/market'

export function MarketBreakoutWidget() {
  const setSelectedSymbol = useAppStore((s) => s.setSelectedSymbol)
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['breakouts'],
    queryFn: getBreakouts,
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <div className="flex h-full flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} style={{ height: '40px' }} />
        ))}
      </div>
    )
  }

  if (isError) {
    return <ErrorState onRetry={() => refetch()} />
  }

  if (!data || data.scanDate === null) {
    return <EmptyState title="Waiting for today's scan" />
  }

  if (data.items.length === 0) {
    return <EmptyState title="No breakouts today" />
  }

  return (
    <div className="h-full overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Ticker</TableHead>
            <TableHead>Company</TableHead>
            <TableHead className="text-right">Close</TableHead>
            <TableHead className="text-right">% Above MA150</TableHead>
            <TableHead className="w-8" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((item) => (
            <BreakoutRow
              key={item.ticker}
              item={item}
              onSelect={() => setSelectedSymbol(item.ticker)}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function BreakoutRow({
  item,
  onSelect,
}: {
  item: BreakoutItem
  onSelect: () => void
}) {
  const { ticker, companyName, closePrice, pctAboveMa150 } = item
  const queryClient = useQueryClient()
  const [added, setAdded] = useState(false)

  const addMutation = useMutation({
    mutationFn: () => addStock(ticker),
    onSuccess: () => {
      setAdded(true)
      queryClient.invalidateQueries({ queryKey: ['signals'] })
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'DUPLICATE') {
        setAdded(true)
      }
    },
  })

  const isPending = addMutation.isPending

  return (
    <TableRow onClick={onSelect} className="cursor-pointer">
      <TableCell className="font-bold">{ticker}</TableCell>
      <TableCell className="text-muted-foreground">{companyName}</TableCell>
      <TableCell
        className="text-right"
        style={{ fontFamily: 'var(--font-family-numeric)' }}
      >
        ${closePrice.toFixed(2)}
      </TableCell>
      <TableCell
        className="text-right"
        style={{
          fontFamily: 'var(--font-family-numeric)',
          color: 'var(--color-change-positive)',
        }}
      >
        +{pctAboveMa150.toFixed(1)}%
      </TableCell>
      <TableCell onClick={(e) => e.stopPropagation()}>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-6 w-6 rounded-full"
          aria-label={added ? `${ticker} 已加入 watchlist` : `添加 ${ticker} 到 watchlist`}
          disabled={isPending || added}
          onClick={() => addMutation.mutate()}
        >
          {isPending ? (
            <Loader2 size={12} className="animate-spin" />
          ) : added ? (
            <Check size={12} className="text-muted-foreground" />
          ) : (
            <Plus size={12} />
          )}
        </Button>
      </TableCell>
    </TableRow>
  )
}
