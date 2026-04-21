import { useMemo, useState } from 'react'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { BreakoutItem, SignalType } from '@/types/market'

type TabKey = 'stage' | 'pullback'

const TAB_SIGNALS: Record<TabKey, readonly SignalType[]> = {
  stage: ['a1_stage_breakout', 'a2_slope_flip'],
  pullback: ['b2_ma_pullback'],
}

const SIGNAL_LABEL: Record<SignalType, string> = {
  legacy_crossover: 'Legacy',
  a1_stage_breakout: 'A1 Breakout',
  a2_slope_flip: 'A2 Slope Flip',
  b2_ma_pullback: 'B2 Pullback',
}

export function MarketBreakoutWidget() {
  const [tab, setTab] = useState<TabKey>('stage')

  return (
    <Tabs
      value={tab}
      onValueChange={(v) => setTab(v as TabKey)}
      className="flex h-full flex-col gap-1"
      style={{ marginTop: '-5px', marginLeft: '-5px' }}
    >
      <TabsList
        className="rounded-full p-[2px] text-[10px]"
        style={{ height: 29 }}
      >
        <TabsTrigger
          value="stage"
          className="rounded-full px-[4px] py-0 text-[10px]"
        >
          Breakout
        </TabsTrigger>
        <TabsTrigger
          value="pullback"
          className="rounded-full px-[4px] py-0 text-[10px]"
        >
          Pullback
        </TabsTrigger>
      </TabsList>
      <TabsContent value="stage" className="min-h-0 flex-1">
        <BreakoutPane signalTypes={TAB_SIGNALS.stage} emptyLabel="No stage breakouts today" />
      </TabsContent>
      <TabsContent value="pullback" className="min-h-0 flex-1">
        <BreakoutPane signalTypes={TAB_SIGNALS.pullback} emptyLabel="No pullback bounces today" />
      </TabsContent>
    </Tabs>
  )
}

function BreakoutPane({
  signalTypes,
  emptyLabel,
}: {
  signalTypes: readonly SignalType[]
  emptyLabel: string
}) {
  const setSelectedSymbol = useAppStore((s) => s.setSelectedSymbol)
  const typesKey = useMemo(() => [...signalTypes].sort().join(','), [signalTypes])
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['breakouts', typesKey],
    queryFn: () => getBreakouts(signalTypes),
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

  if (isError) return <ErrorState onRetry={() => refetch()} />

  if (!data || data.scanDate === null) {
    return <EmptyState title="Waiting for today's scan" />
  }

  if (data.items.length === 0) return <EmptyState title={emptyLabel} />

  const showSignalCol = signalTypes.length > 1

  return (
    <div className="h-full overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Ticker</TableHead>
            <TableHead>Company</TableHead>
            {showSignalCol && <TableHead>Signal</TableHead>}
            <TableHead className="text-right">Close</TableHead>
            <TableHead className="text-right">% Above MA150</TableHead>
            <TableHead className="text-right">Vol×20d</TableHead>
            <TableHead className="w-8" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((item) => (
            <BreakoutRow
              key={`${item.ticker}-${item.signalType}`}
              item={item}
              showSignalCol={showSignalCol}
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
  showSignalCol,
  onSelect,
}: {
  item: BreakoutItem
  showSignalCol: boolean
  onSelect: () => void
}) {
  const { ticker, companyName, signalType, closePrice, pctAboveMa150, volumeRatio20 } = item
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
    <TableRow onClick={onSelect} className="cursor-pointer [&>td]:py-[7px]">
      <TableCell className="font-bold">{ticker}</TableCell>
      <TableCell className="text-muted-foreground">{companyName}</TableCell>
      {showSignalCol && (
        <TableCell className="text-xs text-muted-foreground">
          {SIGNAL_LABEL[signalType]}
        </TableCell>
      )}
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
      <TableCell
        className="text-right text-muted-foreground"
        style={{ fontFamily: 'var(--font-family-numeric)' }}
      >
        {volumeRatio20 != null ? `${volumeRatio20.toFixed(2)}×` : '—'}
      </TableCell>
      <TableCell onClick={(e) => e.stopPropagation()}>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-5 w-5 rounded-full"
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
