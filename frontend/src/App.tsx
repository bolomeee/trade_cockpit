import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { TopNav } from '@/components/features/topnav/TopNav'
import { MarketOverviewBar } from '@/components/features/market-overview/MarketOverviewBar'

const Workbench = lazy(() => import('@/workbench/Workbench'))
const Journal = lazy(() => import('@/pages/Journal'))
const Logs = lazy(() => import('@/pages/Logs'))
const News = lazy(() => import('@/pages/News'))

export default function App() {
  return (
    <div className="min-h-screen">
      <TopNav />
      <MarketOverviewBar />
      <main>
        <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<Workbench />} />
            <Route path="/journal" element={<Journal />} />
            <Route path="/news" element={<News />} />
            <Route path="/logs" element={<Logs />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}
