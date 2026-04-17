import { RefreshCw } from 'lucide-react'

interface RefreshButtonProps {
  isRefreshing: boolean
  onClick: () => void
}

export function RefreshButton({ isRefreshing, onClick }: RefreshButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isRefreshing}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 'var(--spacing-2)',
        height: '32px',
        padding: '0 var(--spacing-3)',
        borderRadius: 'var(--radius-button)',
        border: '1px solid var(--color-border)',
        backgroundColor: 'var(--color-card, #fff)',
        color: 'var(--color-text-primary)',
        fontSize: 'var(--font-size-body)',
        cursor: isRefreshing ? 'not-allowed' : 'pointer',
        opacity: isRefreshing ? 0.7 : 1,
      }}
    >
      <RefreshCw
        size={14}
        style={{
          animation: isRefreshing ? 'spin 1s linear infinite' : undefined,
        }}
      />
      <span>Refresh Data</span>
    </button>
  )
}
