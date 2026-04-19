import type { LayoutItem } from 'react-grid-layout'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type LayoutStore = {
  layout: LayoutItem[]
  setLayout: (layout: LayoutItem[]) => void
  reset: (defaultLayout: LayoutItem[]) => void
}

export const useLayoutStore = create<LayoutStore>()(
  persist(
    (set) => ({
      layout: [],
      setLayout: (layout) => set({ layout }),
      reset: (defaultLayout) => set({ layout: defaultLayout }),
    }),
    {
      name: 'ma150.workbench.layouts.v5',
      version: 5,
    },
  ),
)
