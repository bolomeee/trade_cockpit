import { useEffect } from 'react'
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

  return (
    <div className="p-4">
      <div ref={containerRef}>
        {mounted && layout.length > 0 && (
          <ReactGridLayout
            width={width}
            layout={layout}
            gridConfig={{ cols: 12, rowHeight: 40, margin: [12, 12] }}
            dragConfig={{ enabled: true, handle: '.widget-handle' }}
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
                      className="widget-handle flex h-[18px] shrink-0 cursor-grab items-center border-b border-border px-2 active:cursor-grabbing"
                      style={{ backgroundColor: '#ebf2fa' }}
                    >
                      <span className="text-xs text-foreground">{manifest.title}</span>
                    </div>
                    <div className="flex-1 overflow-auto p-4">
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
