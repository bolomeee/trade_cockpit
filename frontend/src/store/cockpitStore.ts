import { create } from 'zustand'

type CockpitStore = {
  selectedTicker: string | null
  setSelectedTicker: (ticker: string | null) => void
}

export const useCockpitStore = create<CockpitStore>()((set) => ({
  selectedTicker: null,
  setSelectedTicker: (ticker) => set({ selectedTicker: ticker }),
}))
