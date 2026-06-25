import { useEffect } from 'react'
import { X } from 'lucide-react'
import ReactGridLayout, {
  useContainerWidth,
  verticalCompactor,
  type Layout,
} from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import { COCKPIT_WIDGET_REGISTRY, getCockpitDefaultLayout } from './CockpitRegistry'
import { useCockpitLayoutStore } from './useCockpitLayoutStore'

export default function CockpitShell() {
  const layout = useCockpitLayoutStore((s) => s.layout)
  const setLayout = useCockpitLayoutStore((s) => s.setLayout)
  const { width, containerRef, mounted } = useContainerWidth()

  useEffect(() => {
    if (layout.length === 0) setLayout(getCockpitDefaultLayout())
  }, [layout.length, setLayout])

  const handleChange = (next: Layout) => {
    setLayout(next.map((i) => ({ ...i })))
  }

  const handleClose = (id: string) => {
    setLayout(layout.filter((item) => item.i !== id))
  }

  return (
    <div className="p-4">
      <div ref={containerRef}>
        {mounted && layout.length > 0 && (
          <ReactGridLayout
            width={width}
            layout={layout}
            gridConfig={{ cols: 12, rowHeight: 32, margin: [8, 8] }}
            dragConfig={{ enabled: true, handle: '.widget-handle' }}
            resizeConfig={{ handles: ['se', 'sw', 'nw'] }}
            compactor={verticalCompactor}
            onLayoutChange={handleChange}
          >
            {layout.map((item) => {
              const manifest = COCKPIT_WIDGET_REGISTRY[item.i]
              if (!manifest) return <div key={item.i} />
              const Widget = manifest.component
              return (
                <div key={item.i}>
                  <div className="flex h-full flex-col overflow-hidden rounded border border-border bg-card shadow-sm">
                    <div
                      className="widget-handle flex h-[14px] shrink-0 cursor-grab items-center justify-between border-b border-border px-2 active:cursor-grabbing"
                      style={{ backgroundColor: 'var(--color-widget-header)' }}
                    >
                      <span className="text-xs text-foreground">{manifest.title}</span>
                      <button
                        type="button"
                        aria-label={`关闭 ${manifest.title}`}
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleClose(item.i)
                        }}
                        className="flex h-3 w-3 items-center justify-center text-muted-foreground hover:text-foreground"
                      >
                        <X size={10} strokeWidth={2} />
                      </button>
                    </div>
                    <div className="flex-1 overflow-auto">
                      <Widget />
                    </div>
                  </div>
                </div>
              )
            })}
          </ReactGridLayout>
        )}
      </div>
    </div>
  )
}
