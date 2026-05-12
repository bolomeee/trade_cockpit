import type { LayoutItem } from 'react-grid-layout'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type CockpitLayoutStore = {
  layout: LayoutItem[]
  setLayout: (layout: LayoutItem[]) => void
  reset: (defaultLayout: LayoutItem[]) => void
}

export const useCockpitLayoutStore = create<CockpitLayoutStore>()(
  persist(
    (set) => ({
      layout: [],
      setLayout: (layout) => set({ layout }),
      reset: (defaultLayout) => set({ layout: defaultLayout }),
    }),
    {
      name: 'ma150.cockpit.layouts.v1',
      version: 1,
    },
  ),
)
