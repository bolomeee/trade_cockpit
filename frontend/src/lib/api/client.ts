const BASE = '/api'

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  const json = await res.json()
  if (!res.ok) {
    throw new Error(json.error?.message ?? `HTTP ${res.status}`)
  }
  return json.data as T
}
