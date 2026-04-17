const BASE = '/api'

export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  const json = await res.json().catch(() => ({}))
  if (!res.ok) {
    const code = json?.error?.code ?? 'UNKNOWN'
    const message = json?.error?.message ?? `HTTP ${res.status}`
    throw new ApiError(code, message, res.status)
  }
  return json.data as T
}
