import { NavLink } from 'react-router-dom'

import { useRefreshStatus } from '@/hooks/useRefreshStatus'
import { RefreshButton } from './RefreshButton'

const NAV_LINKS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/journal', label: 'Journal', end: false },
  { to: '/logs', label: 'Logs', end: false },
] as const

function formatLastRefresh(iso: string | null): string {
  if (!iso) return 'Last refresh: —'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Last refresh: —'
  const time = d.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  })
  return `Last refresh: ${time}`
}

export function TopNav() {
  const { lastRefreshedAt, isRefreshing, refresh } = useRefreshStatus()

  return (
    <nav
      style={{
        height: '64px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 'var(--spacing-6)',
        padding: '0 var(--spacing-6)',
        backgroundColor: 'var(--color-background)',
        borderBottom: '1px solid var(--color-border)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-6)' }}>
        <span
          style={{
            fontSize: 'var(--font-size-title)',
            fontWeight: 'var(--font-weight-bold)',
            color: 'var(--color-text-primary)',
          }}
        >
          MA150 Tracker
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-4)' }}>
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              style={({ isActive }) => ({
                fontSize: 'var(--font-size-body)',
                color: isActive ? 'var(--color-nav-active)' : 'var(--color-nav-inactive)',
                textDecoration: 'none',
                fontWeight: isActive ? 'var(--font-weight-bold)' : 'var(--font-weight-regular)',
              })}
            >
              {link.label}
            </NavLink>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)' }}>
        <span
          style={{
            fontSize: 'var(--font-size-caption)',
            color: 'var(--color-text-secondary)',
          }}
        >
          {formatLastRefresh(lastRefreshedAt)}
        </span>
        <RefreshButton isRefreshing={isRefreshing} onClick={refresh} />
      </div>
    </nav>
  )
}
