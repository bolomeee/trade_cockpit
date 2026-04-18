import { useEffect } from 'react'
import ReactGridLayout, {
  useContainerWidth,
  verticalCompactor,
  type Layout,
} from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import { getDefaultLayout, WIDGET_REGISTRY } from './WidgetRegistry'
import { WidgetShell } from './WidgetShell'
import { useLayoutStore } from './useLayoutStore'

export default function Workbench() {
  const layout = useLayoutStore((s) => s.layout)
  const setLayout = useLayoutStore((s) => s.setLayout)
  const reset = useLayoutStore((s) => s.reset)
  const { width, containerRef, mounted } = useContainerWidth()

  useEffect(() => {
    if (layout.length === 0) setLayout(getDefaultLayout())
  }, [layout.length, setLayout])

  const handleChange = (next: Layout) => {
    setLayout(next.map((i) => ({ ...i })))
  }

  const handleReset = () => reset(getDefaultLayout())

  return (
    <div className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Workbench</h1>
        <button
          type="button"
          onClick={handleReset}
          className="rounded border border-border bg-background px-3 py-1 text-sm hover:bg-muted"
        >
          重置布局
        </button>
      </div>
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
              const manifest = WIDGET_REGISTRY[item.i]
              if (!manifest) return <div key={item.i} />
              const Widget = manifest.component
              return (
                <div key={item.i}>
                  <WidgetShell title={manifest.title}>
                    <Widget />
                  </WidgetShell>
                </div>
              )
            })}
          </ReactGridLayout>
        )}
      </div>
    </div>
  )
}
