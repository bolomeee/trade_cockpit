import type { LayoutItem } from 'react-grid-layout'
import { apiFetch } from './client'

type PageType = 'workbench' | 'cockpit' | 'news'

export function loadLayout(page: PageType): Promise<LayoutItem[]> {
  return apiFetch<LayoutItem[]>(`/layouts/${page}`)
}

export async function saveLayout(page: PageType, layout: LayoutItem[]): Promise<void> {
  await apiFetch<null>(`/layouts/${page}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(layout),
  })
}
