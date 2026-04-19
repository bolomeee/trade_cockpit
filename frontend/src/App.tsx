import { Route, Routes, useLocation } from 'react-router-dom'
import Dashboard from '@/pages/Dashboard'
import Journal from '@/pages/Journal'
import Logs from '@/pages/Logs'
import Workbench from '@/workbench/Workbench'
import { TopNav } from '@/components/features/topnav/TopNav'
import { MarketOverviewBar } from '@/components/features/market-overview/MarketOverviewBar'
import { ResetLayoutButton } from '@/workbench/ResetLayoutButton'

export default function App() {
  const { pathname } = useLocation()
  const showResetLayout = pathname === '/workbench'

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
          <Route path="/" element={<Dashboard />} />
          <Route path="/journal" element={<Journal />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/workbench" element={<Workbench />} />
        </Routes>
      </main>
    </div>
  )
}
