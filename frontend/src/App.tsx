import { Route, Routes, useLocation } from 'react-router-dom'
import Journal from '@/pages/Journal'
import Logs from '@/pages/Logs'
import Workbench from '@/workbench/Workbench'
import { TopNav } from '@/components/features/topnav/TopNav'
import { MarketOverviewBar } from '@/components/features/market-overview/MarketOverviewBar'
import { ResetLayoutButton } from '@/workbench/ResetLayoutButton'

export default function App() {
  const { pathname } = useLocation()
  const showResetLayout = pathname === '/'

  return (
    <div className="min-h-screen">
      <TopNav />
      <div style={{ position: 'relative' }}>
        <MarketOverviewBar />
        {showResetLayout && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              right: 'var(--spacing-6)',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <ResetLayoutButton />
          </div>
        )}
      </div>
      <main>
        <Routes>
          <Route path="/" element={<Workbench />} />
          <Route path="/journal" element={<Journal />} />
          <Route path="/logs" element={<Logs />} />
        </Routes>
      </main>
    </div>
  )
}
