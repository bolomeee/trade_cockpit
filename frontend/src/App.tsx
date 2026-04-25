import { lazy, Suspense } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { TopNav } from '@/components/features/topnav/TopNav'
import { MarketOverviewBar } from '@/components/features/market-overview/MarketOverviewBar'

const Workbench = lazy(() => import('@/workbench/Workbench'))
const Cockpit = lazy(() => import('@/pages/Cockpit'))
const Journal = lazy(() => import('@/pages/Journal'))
const Logs = lazy(() => import('@/pages/Logs'))
const News = lazy(() => import('@/pages/News'))

export default function App() {
  const { pathname } = useLocation()
  return (
    <div className="min-h-screen">
      <TopNav />
      {pathname !== '/cockpit' && <MarketOverviewBar />}
      <main>
        <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<Workbench />} />
            <Route path="/cockpit" element={<Cockpit />} />
            <Route path="/journal" element={<Journal />} />
            <Route path="/news" element={<News />} />
            <Route path="/logs" element={<Logs />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}
