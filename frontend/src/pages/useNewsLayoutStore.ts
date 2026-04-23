import type { LayoutItem } from 'react-grid-layout'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type NewsLayoutStore = {
  layout: LayoutItem[]
  setLayout: (layout: LayoutItem[]) => void
  reset: (defaultLayout: LayoutItem[]) => void
}

export const useNewsLayoutStore = create<NewsLayoutStore>()(
  persist(
    (set) => ({
      layout: [],
      setLayout: (layout) => set({ layout }),
      reset: (defaultLayout) => set({ layout: defaultLayout }),
    }),
    {
      name: 'ma150.news.layouts.v3',
      version: 3,
    },
  ),
)
