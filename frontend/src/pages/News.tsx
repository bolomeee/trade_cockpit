import { useEffect, useState } from 'react'
import { AiNewsSummaryBar } from '@/components/news/AiNewsSummaryBar'
import ReactGridLayout, {
  useContainerWidth,
  verticalCompactor,
  type Layout,
} from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import { getNewsDefaultLayout, WIDGET_REGISTRY } from '@/workbench/WidgetRegistry'
import { WidgetShell } from '@/workbench/WidgetShell'
import { NewsWidget } from '@/workbench/widgets/NewsWidget'
import { ArticleDetailWidget } from '@/workbench/widgets/ArticleDetailWidget'
import { useAppStore } from '@/store/useAppStore'
import type { NewsArticle } from '@/types/news'
import { useNewsLayoutStore } from './useNewsLayoutStore'

export default function News() {
  const layout = useNewsLayoutStore((s) => s.layout)
  const setLayout = useNewsLayoutStore((s) => s.setLayout)
  const { width, containerRef, mounted } = useContainerWidth()
  const [selectedArticle, setSelectedArticle] = useState<NewsArticle | null>(null)
  const setSelectedSymbol = useAppStore((s) => s.setSelectedSymbol)

  useEffect(() => {
    if (layout.length === 0) {
      setLayout(getNewsDefaultLayout())
      return
    }
    // Migration: ensure the News Detail widget exists for users with a
    // persisted layout from before it was added (preserves custom layouts).
    if (!layout.some((item) => item.i === 'news.detail')) {
      const detail = WIDGET_REGISTRY['news.detail']
      setLayout([...layout, { i: detail.id, ...detail.defaultLayout }])
    }
  }, [layout, setLayout])

  const handleChange = (next: Layout) => {
    setLayout(next.map((i) => ({ ...i })))
  }

  const handleClose = (id: string) => {
    setLayout(layout.filter((item) => item.i !== id))
  }

  return (
    <div className="p-4">
      <AiNewsSummaryBar />
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
              return (
                <div key={item.i}>
                  <WidgetShell title={manifest.title} onClose={() => handleClose(item.i)} noPaddingRight={manifest.noPaddingRight}>
                    {item.i === 'news.table' ? (
                      <NewsWidget
                        onOpenArticle={setSelectedArticle}
                        onSelectTicker={setSelectedSymbol}
                      />
                    ) : item.i === 'news.detail' ? (
                      <ArticleDetailWidget
                        article={selectedArticle}
                        onSelectTicker={setSelectedSymbol}
                      />
                    ) : (
                      <manifest.component />
                    )}
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
