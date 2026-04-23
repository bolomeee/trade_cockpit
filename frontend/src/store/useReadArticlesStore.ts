import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type ReadArticlesStore = {
  readKeys: Record<string, true>
  markAsRead: (key: string) => void
  isRead: (key: string) => boolean
}

export const useReadArticlesStore = create<ReadArticlesStore>()(
  persist(
    (set, get) => ({
      readKeys: {},
      markAsRead: (key) => {
        if (!get().readKeys[key]) {
          set((s) => ({ readKeys: { ...s.readKeys, [key]: true } }))
        }
      },
      isRead: (key) => Boolean(get().readKeys[key]),
    }),
    { name: 'ma150.news.read.v1' },
  ),
)
