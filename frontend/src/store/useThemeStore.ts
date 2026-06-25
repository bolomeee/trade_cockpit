import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Theme = 'light' | 'dark'

/** First-visit default: follow the OS preference. Guarded for jsdom (no matchMedia). */
function systemTheme(): Theme {
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return 'light'
}

type ThemeStore = {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set, get) => ({
      theme: systemTheme(), // overridden by persisted value when present
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set({ theme: get().theme === 'dark' ? 'light' : 'dark' }),
    }),
    { name: 'ma150.theme.v1' },
  ),
)

/**
 * Apply/remove the `.dark` class on <html>. Wired up in main.tsx (module scope,
 * so it survives StrictMode). Kept here with no import-time side effect so it is
 * unit-testable and co-located with the theme it reflects.
 */
export function applyThemeClass(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}
