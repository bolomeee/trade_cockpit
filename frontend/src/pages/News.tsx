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
import { ArticleModal } from '@/components/common/ArticleModal'
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
    if (layout.length === 0) setLayout(getNewsDefaultLayout())
  }, [layout.length, setLayout])

  const handleChange = (next: Layout) => {
    setLayout(next.map((i) => ({ ...i })))
  }

  const handleClose = (id: string) => {
    setLayout(layout.filter((item) => item.i !== id))
  }

  const handleSelectTicker = (ticker: string) => {
    setSelectedSymbol(ticker)
    setSelectedArticle(null)
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
      <ArticleModal
        article={selectedArticle}
        onClose={() => setSelectedArticle(null)}
        onSelectTicker={handleSelectTicker}
      />
    </div>
  )
}
