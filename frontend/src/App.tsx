import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { TopNav } from '@/components/features/topnav/TopNav'
import { TooltipProvider } from '@/components/ui/tooltip'

const Workbench = lazy(() => import('@/workbench/Workbench'))
const Cockpit = lazy(() => import('@/pages/Cockpit'))
const Journal = lazy(() => import('@/pages/Journal'))
const Logs = lazy(() => import('@/pages/Logs'))
const News = lazy(() => import('@/pages/News'))

export default function App() {
  return (
    <TooltipProvider>
    <div className="min-h-screen">
      <TopNav />
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
    </TooltipProvider>
  )
}
