import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Trash2 } from 'lucide-react'

import type { WatchlistItem } from '@/types/watchlist'
import { SignalBadge } from './SignalBadge'
import { removeStock } from '@/lib/api/watchlist'
import { ApiError } from '@/lib/api/client'
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

interface SignalCardProps {
  stock: WatchlistItem
  onClick: () => void
}

export function SignalCard({ stock, onClick }: SignalCardProps) {
  const { ticker, name, latestSignal } = stock
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const deleteMutation = useMutation({
    mutationFn: () => removeStock(ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      setDialogOpen(false)
      setDeleteError(null)
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'NOT_FOUND') {
        queryClient.invalidateQueries({ queryKey: ['watchlist'] })
        setDialogOpen(false)
        setDeleteError(null)
        return
      }
      setDeleteError('删除失败，请重试')
    },
  })

  const distancePct = latestSignal?.distancePct ?? null
  const distanceColor =
    distancePct !== null
      ? distancePct >= 0
        ? 'var(--color-change-positive)'
        : 'var(--color-change-negative)'
      : 'var(--color-text-secondary)'

  const isDeleting = deleteMutation.isPending

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={e => e.key === 'Enter' && onClick()}
      className="group"
      style={{
        position: 'relative',
        backgroundColor: 'var(--color-card)',
        borderRadius: 'var(--radius-card)',
        boxShadow: 'var(--shadow-card)',
        border: '1px solid var(--color-border)',
        padding: 'var(--spacing-card-padding-sm)',
        cursor: isDeleting ? 'not-allowed' : 'pointer',
        transition: 'box-shadow 150ms ease, opacity 150ms ease',
        minHeight: '122px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        opacity: isDeleting ? 0.5 : 1,
        pointerEvents: isDeleting ? 'none' : 'auto',
      }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = 'var(--shadow-hover-card)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = 'var(--shadow-card)')}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
        <span style={{ fontWeight: 'var(--font-weight-bold)', fontSize: 'var(--font-size-subtitle)' }}>
          {ticker}
        </span>
        <SignalBadge signalType={latestSignal?.signalType ?? null} />
      </div>

      <p style={{ fontSize: 'var(--font-size-body)', color: 'var(--color-text-secondary)', margin: '4px 0 0' }}>
        {name}
      </p>

      <div style={{ marginTop: '12px' }}>
        {distancePct !== null ? (
          <span style={{ fontSize: 'var(--font-size-caption)', color: distanceColor, fontFamily: 'var(--font-family-numeric)' }}>
            {distancePct >= 0 ? '+' : ''}{distancePct.toFixed(1)}% MA150
          </span>
        ) : (
          <span style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }}>
            —
          </span>
        )}
      </div>

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
            onClick={(e) => { e.stopPropagation() }}
            className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
            style={{
              position: 'absolute',
              top: 'var(--spacing-card-padding-sm)',
              right: 'var(--spacing-card-padding-sm)',
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              color: 'var(--color-text-secondary)',
              transition: 'opacity 150ms ease, color 150ms ease',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-error)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-secondary)' }}
          >
            <Trash2 size={16} />
          </button>
        </AlertDialogTrigger>
        <AlertDialogContent onClick={(e) => e.stopPropagation()}>
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
    </div>
  )
}
