import { RotateCcw } from 'lucide-react'

import { getCockpitDefaultLayout } from './CockpitRegistry'
import { useCockpitLayoutStore } from './useCockpitLayoutStore'

export function CockpitResetLayoutButton() {
  const reset = useCockpitLayoutStore((s) => s.reset)

  return (
    <button
      type="button"
      onClick={() => reset(getCockpitDefaultLayout())}
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
