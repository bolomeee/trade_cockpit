import type { ReactNode } from 'react'

type WidgetShellProps = {
  title: string
  children: ReactNode
}

export function WidgetShell({ title, children }: WidgetShellProps) {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm">
      <div className="widget-handle flex h-9 shrink-0 cursor-grab items-center justify-between border-b border-border bg-muted px-3 active:cursor-grabbing">
        <span className="text-sm font-semibold text-foreground">{title}</span>
      </div>
      <div className="flex-1 overflow-auto p-4">{children}</div>
    </div>
  )
}
