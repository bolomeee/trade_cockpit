import { create } from 'zustand'

type AppStore = {
  selectedSymbol: string | null
  setSelectedSymbol: (symbol: string | null) => void
}

export const useAppStore = create<AppStore>((set) => ({
  selectedSymbol: null,
  setSelectedSymbol: (selectedSymbol) => set({ selectedSymbol }),
}))
