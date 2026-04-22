export interface FormatPercentOptions {
  digits?: number
  fallback?: string
}

export function formatPercent(
  value: number | null | undefined,
  options: FormatPercentOptions = {},
): string {
  const { digits = 2, fallback = '—' } = options
  if (value == null || !Number.isFinite(value)) return fallback
  return `${value.toFixed(digits)}%`
}
