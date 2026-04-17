import { Route, Routes } from 'react-router-dom'
import Dashboard from '@/pages/Dashboard'
import Journal from '@/pages/Journal'
import Logs from '@/pages/Logs'
import { TopNav } from '@/components/features/topnav/TopNav'

export default function App() {
  return (
    <div className="min-h-screen">
      <TopNav />
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/journal" element={<Journal />} />
          <Route path="/logs" element={<Logs />} />
        </Routes>
      </main>
    </div>
  )
}
