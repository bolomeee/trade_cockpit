import { Link, Route, Routes } from 'react-router-dom'
import Dashboard from '@/pages/Dashboard'
import Journal from '@/pages/Journal'
import Logs from '@/pages/Logs'

export default function App() {
  return (
    <div className="min-h-screen">
      <nav className="flex gap-4 border-b p-4 text-sm">
        <Link to="/">Dashboard</Link>
        <Link to="/journal">Journal</Link>
        <Link to="/logs">Logs</Link>
      </nav>
      <main className="p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/journal" element={<Journal />} />
          <Route path="/logs" element={<Logs />} />
        </Routes>
      </main>
    </div>
  )
}
