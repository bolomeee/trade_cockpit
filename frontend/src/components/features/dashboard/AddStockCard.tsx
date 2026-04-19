import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover'
import { searchStocks } from '@/lib/api/stocks'
import { addStock } from '@/lib/api/watchlist'
import { ApiError } from '@/lib/api/client'
import type { StockSearchItem } from '@/types/stocks'

const SEARCH_LIMIT = 10

export function AddStockCard() {
  const queryClient = useQueryClient()
  const [input, setInput] = useState('')
  const [query, setQuery] = useState<string | null>(null)
  const [itemError, setItemError] = useState<{ ticker: string; message: string } | null>(null)
  const [pendingTicker, setPendingTicker] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const searchQuery = useQuery({
    queryKey: ['stock-search', query],
    queryFn: () => searchStocks(query!, SEARCH_LIMIT),
    enabled: query !== null && query.length > 0,
    staleTime: 60 * 1000,
    retry: false,
  })

  const addMutation = useMutation({
    mutationFn: (ticker: string) => addStock(ticker),
    onMutate: (ticker) => {
      setPendingTicker(ticker)
      setItemError(null)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      queryClient.invalidateQueries({ queryKey: ['signals'] })
      setInput('')
      setQuery(null)
      setPendingTicker(null)
      inputRef.current?.focus()
    },
    onError: (err, ticker) => {
      const code = err instanceof ApiError ? err.code : 'UNKNOWN'
      let message = '添加失败，请重试'
      if (code === 'DUPLICATE') message = '该股票已在 watchlist'
      else if (code === 'NOT_FOUND') message = '股票代码无效'
      setItemError({ ticker, message })
      setPendingTicker(null)
    },
  })

  useEffect(() => {
    const trimmed = input.trim()
    if (trimmed.length === 0) {
      setQuery(null)
      return
    }
    const t = setTimeout(() => {
      setQuery(trimmed)
      setItemError(null)
    }, 200)
    return () => clearTimeout(t)
  }, [input])

  const isOpen = query !== null && query.length > 0

  return (
    <Popover open={isOpen} onOpenChange={(open) => { if (!open) setQuery(null) }}>
      <PopoverAnchor asChild>
        <Input
          ref={inputRef}
          value={input}
          placeholder="Search ticker or name (e.g. OXY)"
          onChange={(e) => setInput(e.target.value)}
        />
      </PopoverAnchor>
      <PopoverContent
        align="start"
        sideOffset={4}
        style={{ width: '260px', padding: 0 }}
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <SearchResults
          isLoading={searchQuery.isLoading}
          isError={searchQuery.isError}
          onRetry={() => searchQuery.refetch()}
          items={searchQuery.data ?? []}
          onSelect={(ticker) => addMutation.mutate(ticker)}
          pendingTicker={pendingTicker}
          itemError={itemError}
        />
      </PopoverContent>
    </Popover>
  )
}

interface SearchResultsProps {
  isLoading: boolean
  isError: boolean
  onRetry: () => void
  items: StockSearchItem[]
  onSelect: (ticker: string) => void
  pendingTicker: string | null
  itemError: { ticker: string; message: string } | null
}

function SearchResults({
  isLoading,
  isError,
  onRetry,
  items,
  onSelect,
  pendingTicker,
  itemError,
}: SearchResultsProps) {
  if (isLoading) {
    return (
      <div style={{ padding: 'var(--spacing-3)', display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-body)' }}>
        <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
        <span>搜索中…</span>
      </div>
    )
  }

  if (isError) {
    return (
      <div style={{ padding: 'var(--spacing-3)', fontSize: 'var(--font-size-body)' }}>
        <div style={{ color: 'var(--color-error)', marginBottom: 'var(--spacing-2)' }}>搜索失败</div>
        <button
          onClick={onRetry}
          style={{
            color: 'var(--color-primary)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            fontSize: 'var(--font-size-body)',
          }}
        >
          重试
        </button>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div style={{ padding: 'var(--spacing-3)', color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-body)' }}>
        未找到匹配的股票
      </div>
    )
  }

  return (
    <ul style={{ listStyle: 'none', margin: 0, padding: 'var(--spacing-1)', maxHeight: '280px', overflowY: 'auto' }}>
      {items.map((item) => {
        const isPending = pendingTicker === item.ticker
        const hasError = itemError?.ticker === item.ticker
        return (
          <li key={item.ticker}>
            <button
              type="button"
              disabled={isPending}
              onClick={() => onSelect(item.ticker)}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: 'var(--spacing-2) var(--spacing-3)',
                background: 'none',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: isPending ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 'var(--spacing-2)',
                opacity: isPending ? 0.6 : 1,
                fontSize: 'var(--font-size-body)',
              }}
              onMouseEnter={(e) => { if (!isPending) e.currentTarget.style.backgroundColor = 'var(--color-muted)' }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
            >
              <span style={{ display: 'flex', flexDirection: 'column', gap: '2px', overflow: 'hidden' }}>
                <span style={{ fontWeight: 'var(--font-weight-bold)', color: 'var(--color-text-primary)' }}>
                  {item.ticker}
                </span>
                <span style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {item.name}{item.exchange ? ` · ${item.exchange}` : ''}
                </span>
              </span>
              {isPending && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite', flexShrink: 0 }} />}
            </button>
            {hasError && (
              <div style={{ padding: '0 var(--spacing-3) var(--spacing-2)', color: 'var(--color-error)', fontSize: 'var(--font-size-caption)' }}>
                {itemError!.message}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
