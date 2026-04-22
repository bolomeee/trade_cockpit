import type { ReactNode } from 'react'
import { X } from 'lucide-react'

type WidgetShellProps = {
  title: string
  children: ReactNode
  onClose?: () => void
}

export function WidgetShell({ title, children, onClose }: WidgetShellProps) {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded border border-border bg-card shadow-sm">
      <div
        className="widget-handle flex h-[18px] shrink-0 cursor-grab items-center justify-between border-b border-border px-2 active:cursor-grabbing"
        style={{ backgroundColor: '#ebf2fa' }}
      >
        <span className="text-xs text-foreground">{title}</span>
        {onClose && (
          <button
            type="button"
            aria-label={`关闭 ${title}`}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation()
              onClose()
            }}
            className="flex h-3 w-3 items-center justify-center text-muted-foreground hover:text-foreground"
          >
            <X size={10} strokeWidth={2} />
          </button>
        )}
      </div>
      <div className="flex-1 overflow-auto p-4">{children}</div>
    </div>
  )
}
