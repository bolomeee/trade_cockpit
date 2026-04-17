import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, X } from 'lucide-react'

import type { SignalBoardItem } from '@/types/signal'
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
  stock: SignalBoardItem
  onClick: () => void
}

export function SignalCard({ stock, onClick }: SignalCardProps) {
  const { ticker, name, signalType, closePrice, distancePct } = stock
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const invalidateAfterDelete = () => {
    queryClient.invalidateQueries({ queryKey: ['signals'] })
    queryClient.invalidateQueries({ queryKey: ['watchlist'] })
  }

  const deleteMutation = useMutation({
    mutationFn: () => removeStock(ticker),
    onSuccess: () => {
      invalidateAfterDelete()
      setDialogOpen(false)
      setDeleteError(null)
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'NOT_FOUND') {
        invalidateAfterDelete()
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
        <SignalBadge signalType={signalType} />
      </div>

      <p style={{ fontSize: 'var(--font-size-body)', color: 'var(--color-text-secondary)', margin: '4px 0 0' }}>
        {name}
      </p>

      <div style={{ marginTop: '8px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '8px' }}>
        <span
          style={{
            fontSize: 'var(--font-size-hero)',
            fontFamily: 'var(--font-family-numeric)',
            fontWeight: 'var(--font-weight-bold)',
            color: 'var(--color-text-primary)',
          }}
        >
          {closePrice !== null ? `$${closePrice.toFixed(2)}` : '—'}
        </span>
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
              top: '-8px',
              right: '-8px',
              width: '20px',
              height: '20px',
              borderRadius: '9999px',
              background: 'var(--color-card)',
              border: '1px solid var(--color-border)',
              boxShadow: 'var(--shadow-card)',
              padding: 0,
              cursor: 'pointer',
              color: 'var(--color-text-secondary)',
              transition: 'opacity 150ms ease, color 150ms ease, background-color 150ms ease',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--color-text-on-dark)'
              e.currentTarget.style.backgroundColor = 'var(--color-error)'
              e.currentTarget.style.borderColor = 'var(--color-error)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--color-text-secondary)'
              e.currentTarget.style.backgroundColor = 'var(--color-card)'
              e.currentTarget.style.borderColor = 'var(--color-border)'
            }}
          >
            <X size={12} strokeWidth={2.5} />
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
