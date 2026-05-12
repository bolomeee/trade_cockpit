import { useEffect } from 'react'
import ReactGridLayout, {
  useContainerWidth,
  verticalCompactor,
  type Layout,
} from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import { getWorkbenchDefaultLayout, WIDGET_REGISTRY } from './WidgetRegistry'
import { WidgetShell } from './WidgetShell'
import { useLayoutStore } from './useLayoutStore'

export default function Workbench() {
  const layout = useLayoutStore((s) => s.layout)
  const setLayout = useLayoutStore((s) => s.setLayout)
  const { width, containerRef, mounted } = useContainerWidth()

  useEffect(() => {
    if (layout.length === 0) setLayout(getWorkbenchDefaultLayout())
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
            resizeConfig={{ handles: ['se', 'sw', 'nw'] }}
            compactor={verticalCompactor}
            onLayoutChange={handleChange}
          >
            {layout.map((item) => {
              const manifest = WIDGET_REGISTRY[item.i]
              if (!manifest) return <div key={item.i} />
              const Widget = manifest.component
              return (
                <div key={item.i}>
                  <WidgetShell title={manifest.title} onClose={() => handleClose(item.i)} noPaddingRight={manifest.noPaddingRight}>
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
