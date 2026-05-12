import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { CloudDownload, CloudUpload, Settings } from 'lucide-react'
import { toast } from 'sonner'

import { CockpitResetLayoutButton } from '@/cockpit/CockpitResetLayoutButton'
import { useCockpitLayoutStore } from '@/cockpit/useCockpitLayoutStore'
import { UserSettingsDialog } from '@/cockpit/components/UserSettingsDialog'
import { useRefreshStatus } from '@/hooks/useRefreshStatus'
import { loadLayout, saveLayout } from '@/lib/api/layouts'
import { ResetLayoutButton } from '@/workbench/ResetLayoutButton'
import { useLayoutStore } from '@/workbench/useLayoutStore'
import { Button } from '@/components/ui/button'
import { ButtonGroup } from '@/components/ui/button-group'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { RefreshButton } from './RefreshButton'
import { useAppStore } from '@/store/useAppStore'
import { useNewsArticles } from '@/hooks/useNewsArticles'
import { useNewsLayoutStore } from '@/pages/useNewsLayoutStore'

const NAV_LINKS = [
  { to: '/cockpit', label: 'Cockpit', end: false },
  { to: '/news', label: 'News', end: false },
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
  const { pathname } = useLocation()
  const showResetLayout = pathname === '/'
  const showCockpitReset = pathname === '/cockpit'
  const showNewsSummary = pathname === '/news'
  const showLayoutSync = pathname === '/' || pathname === '/cockpit' || pathname === '/news'
  const [settingsOpen, setSettingsOpen] = useState(false)
  const aiNewsSummaryOpen = useAppStore((s) => s.aiNewsSummaryOpen)
  const setAiNewsSummaryOpen = useAppStore((s) => s.setAiNewsSummaryOpen)
  const { data: newsArticles = [] } = useNewsArticles()
  const isNewsDisabled = showNewsSummary && newsArticles.length === 0

  const handleSaveLayout = async () => {
    let page: 'workbench' | 'cockpit' | 'news'
    let layout
    if (pathname === '/') {
      page = 'workbench'
      layout = useLayoutStore.getState().layout
    } else if (pathname === '/cockpit') {
      page = 'cockpit'
      layout = useCockpitLayoutStore.getState().layout
    } else {
      page = 'news'
      layout = useNewsLayoutStore.getState().layout
    }
    try {
      await saveLayout(page, layout)
      toast('Layout 已保存')
    } catch {
      toast.error('保存失败，请重试')
    }
  }

  const handleLoadLayout = async () => {
    let page: 'workbench' | 'cockpit' | 'news'
    if (pathname === '/') page = 'workbench'
    else if (pathname === '/cockpit') page = 'cockpit'
    else page = 'news'
    try {
      const layout = await loadLayout(page)
      if (layout.length === 0) {
        toast('暂无保存的 Layout')
        return
      }
      if (pathname === '/') useLayoutStore.getState().setLayout(layout)
      else if (pathname === '/cockpit') useCockpitLayoutStore.getState().setLayout(layout)
      else useNewsLayoutStore.getState().setLayout(layout)
      toast('Layout 已导入')
    } catch {
      toast.error('导入失败，请重试')
    }
  }

  return (
    <nav
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
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
        <ButtonGroup>
          {showNewsSummary && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isNewsDisabled || aiNewsSummaryOpen}
                  onClick={() => setAiNewsSummaryOpen(true)}
                >
                  AI Summary
                </Button>
              </TooltipTrigger>
              <TooltipContent>生成 AI 新闻摘要</TooltipContent>
            </Tooltip>
          )}
          <Tooltip>
            <TooltipTrigger asChild>
              <RefreshButton isRefreshing={isRefreshing} onClick={refresh} />
            </TooltipTrigger>
            <TooltipContent>刷新数据</TooltipContent>
          </Tooltip>
          {showResetLayout && (
            <Tooltip>
              <TooltipTrigger asChild>
                <ResetLayoutButton />
              </TooltipTrigger>
              <TooltipContent>重置 Workbench 布局</TooltipContent>
            </Tooltip>
          )}
          {showCockpitReset && (
            <Tooltip>
              <TooltipTrigger asChild>
                <CockpitResetLayoutButton />
              </TooltipTrigger>
              <TooltipContent>重置 Cockpit 布局</TooltipContent>
            </Tooltip>
          )}
          {showCockpitReset && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="outline" size="sm" onClick={() => setSettingsOpen(true)}>
                  <Settings />
                </Button>
              </TooltipTrigger>
              <TooltipContent>用户设置</TooltipContent>
            </Tooltip>
          )}
          {showLayoutSync && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="outline" size="sm" onClick={handleSaveLayout}>
                  <CloudUpload size={14} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>保存当前布局到服务器</TooltipContent>
            </Tooltip>
          )}
          {showLayoutSync && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="outline" size="sm" onClick={handleLoadLayout}>
                  <CloudDownload size={14} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>从服务器导入已保存的布局</TooltipContent>
            </Tooltip>
          )}
        </ButtonGroup>
        {showCockpitReset && (
          <UserSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
        )}
      </div>
    </nav>
  )
}
