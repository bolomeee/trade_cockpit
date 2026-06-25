import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useThemeStore, applyThemeClass } from '../useThemeStore'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('dark')
  useThemeStore.setState({ theme: 'light' })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useThemeStore', () => {
  it('toggleTheme flips light <-> dark', () => {
    useThemeStore.getState().toggleTheme()
    expect(useThemeStore.getState().theme).toBe('dark')
    useThemeStore.getState().toggleTheme()
    expect(useThemeStore.getState().theme).toBe('light')
  })

  it('setTheme persists in the exact shape the index.html FOUC script reads', () => {
    useThemeStore.getState().setTheme('dark')
    const raw = localStorage.getItem('ma150.theme.v1')
    expect(raw).not.toBeNull()
    expect(JSON.parse(raw as string)).toEqual({ state: { theme: 'dark' }, version: 0 })
  })

  it('follows the system preference on first load when nothing is persisted', async () => {
    localStorage.clear()
    vi.resetModules()
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true }))
    const { useThemeStore: freshStore } = await import('../useThemeStore')
    expect(freshStore.getState().theme).toBe('dark')
  })
})

describe('applyThemeClass', () => {
  it('adds/removes the .dark class on <html>', () => {
    applyThemeClass('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    applyThemeClass('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })
})
