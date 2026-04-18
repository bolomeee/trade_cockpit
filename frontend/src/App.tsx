import { Route, Routes } from 'react-router-dom'
import Dashboard from '@/pages/Dashboard'
import Journal from '@/pages/Journal'
import Logs from '@/pages/Logs'
import Workbench from '@/workbench/Workbench'
import { TopNav } from '@/components/features/topnav/TopNav'
import { MarketOverviewBar } from '@/components/features/market-overview/MarketOverviewBar'

export default function App() {
  return (
    <div className="min-h-screen">
      <TopNav />
      <MarketOverviewBar />
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
