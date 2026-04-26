import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Settings } from 'lucide-react'

import { CockpitResetLayoutButton } from '@/cockpit/CockpitResetLayoutButton'
import { UserSettingsDialog } from '@/cockpit/components/UserSettingsDialog'
import { useRefreshStatus } from '@/hooks/useRefreshStatus'
import { ResetLayoutButton } from '@/workbench/ResetLayoutButton'
import { Button } from '@/components/ui/button'
import { ButtonGroup } from '@/components/ui/button-group'
import { RefreshButton } from './RefreshButton'

const NAV_LINKS = [
  { to: '/cockpit', label: 'Cockpit', end: false },
  { to: '/journal', label: 'Journal', end: false },
  { to: '/news', label: 'News', end: false },
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
  const { pathname } = useLocation()
  const showResetLayout = pathname === '/'
  const showCockpitReset = pathname === '/cockpit'
  const [settingsOpen, setSettingsOpen] = useState(false)

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
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--spacing-6)' }}>
        <NavLink
          to="/"
          end
          style={{
            fontSize: 'var(--font-size-title)',
            fontWeight: 'var(--font-weight-bold)',
            color: 'var(--color-text-primary)',
            textDecoration: 'none',
          }}
        >
          MA150 Tracker
        </NavLink>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--spacing-4)' }}>
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
        <ButtonGroup className="has-[>[data-slot=button-group]]:gap-1">
          <ButtonGroup>
            <RefreshButton isRefreshing={isRefreshing} onClick={refresh} />
          </ButtonGroup>
          {showResetLayout && (
            <ButtonGroup>
              <ResetLayoutButton />
            </ButtonGroup>
          )}
          {showCockpitReset && (
            <ButtonGroup>
              <CockpitResetLayoutButton />
            </ButtonGroup>
          )}
          {showCockpitReset && (
            <ButtonGroup>
              <Button variant="outline" size="sm" onClick={() => setSettingsOpen(true)}>
                <Settings />
                Settings
              </Button>
            </ButtonGroup>
          )}
        </ButtonGroup>
        {showCockpitReset && (
          <UserSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
        )}
      </div>
    </nav>
  )
}
