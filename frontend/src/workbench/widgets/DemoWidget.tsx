import { useAppStore } from '@/store/useAppStore'

export function DemoWidget() {
  const { selectedSymbol, setSelectedSymbol } = useAppStore()
  return (
    <div className="flex h-full flex-col gap-2 text-sm">
      <p className="text-muted-foreground">
        Selected symbol: <strong className="text-foreground">{selectedSymbol ?? '(none)'}</strong>
      </p>
      <div className="flex flex-wrap gap-2">
        {['AAPL', 'MSFT', 'NVDA'].map((s) => (
          <button
            key={s}
            type="button"
            className="rounded border border-border bg-background px-2 py-1 text-xs hover:bg-muted"
            onClick={() => setSelectedSymbol(s)}
          >
            {s}
          </button>
        ))}
        <button
          type="button"
          className="rounded border border-border bg-background px-2 py-1 text-xs hover:bg-muted"
          onClick={() => setSelectedSymbol(null)}
        >
          clear
        </button>
      </div>
    </div>
  )
}
