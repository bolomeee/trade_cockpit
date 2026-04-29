import { create } from 'zustand'

type AppStore = {
  selectedSymbol: string | null
  setSelectedSymbol: (symbol: string | null) => void
  aiNewsSummaryOpen: boolean
  setAiNewsSummaryOpen: (open: boolean) => void
}

export const useAppStore = create<AppStore>((set) => ({
  selectedSymbol: null,
  setSelectedSymbol: (selectedSymbol) => set({ selectedSymbol }),
  aiNewsSummaryOpen: false,
  setAiNewsSummaryOpen: (aiNewsSummaryOpen) => set({ aiNewsSummaryOpen }),
}))
