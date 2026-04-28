export function calcDaysUntil(dateIso: string | null): number | null {
  if (!dateIso) return null
  const ms = new Date(dateIso + 'T00:00:00Z').getTime() - Date.now()
  return Math.round(ms / 86400000)
}
