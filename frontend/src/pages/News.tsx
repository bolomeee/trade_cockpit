import { useEffect } from 'react'
import ReactGridLayout, {
  useContainerWidth,
  verticalCompactor,
  type Layout,
} from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import { getNewsDefaultLayout, WIDGET_REGISTRY } from '@/workbench/WidgetRegistry'
import { WidgetShell } from '@/workbench/WidgetShell'
import { useNewsLayoutStore } from './useNewsLayoutStore'

export default function News() {
  const layout = useNewsLayoutStore((s) => s.layout)
  const setLayout = useNewsLayoutStore((s) => s.setLayout)
  const { width, containerRef, mounted } = useContainerWidth()

  useEffect(() => {
    if (layout.length === 0) setLayout(getNewsDefaultLayout())
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
            gridConfig={{ cols: 12, rowHeight: 40, margin: [6, 6] }}
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
                  <WidgetShell title={manifest.title} onClose={() => handleClose(item.i)}>
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
