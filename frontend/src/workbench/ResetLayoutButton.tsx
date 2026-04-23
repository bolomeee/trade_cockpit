import { RotateCcw } from 'lucide-react'
import { getWorkbenchDefaultLayout } from './WidgetRegistry'
import { useLayoutStore } from './useLayoutStore'

export function ResetLayoutButton() {
  const reset = useLayoutStore((s) => s.reset)

  return (
    <button
      type="button"
      onClick={() => reset(getWorkbenchDefaultLayout())}
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
        cursor: 'pointer',
      }}
    >
      <RotateCcw size={14} />
      <span>重置布局</span>
    </button>
  )
}
