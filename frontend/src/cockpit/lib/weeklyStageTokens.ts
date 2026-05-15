export const STAGE_LABELS: Record<number, string> = {
  0: 'Unknown',
  1: 'Base',
  2: 'Advancing',
  3: 'Distribution',
  4: 'Declining',
}

export const STAGE_BG_TOKENS: Record<number, string> = {
  0: '--color-text-muted',
  1: '--color-log-warn',
  2: '--color-change-positive',
  3: '--color-log-warn',
  4: '--color-change-negative',
}

export const STAGE_BG_FALLBACKS: Record<number, string> = {
  0: '#6b7280',
  1: '#f59e0b',
  2: '#10b981',
  3: '#f59e0b',
  4: '#ef4444',
}

export function readStageColor(stage: number | null | undefined): string {
  // stage null/undefined 视作 0（Unknown） — 颜色取 muted
  const key = stage == null ? 0 : stage
  if (typeof window === 'undefined') return STAGE_BG_FALLBACKS[key] ?? STAGE_BG_FALLBACKS[0]
  const v = getComputedStyle(document.documentElement).getPropertyValue(STAGE_BG_TOKENS[key] ?? STAGE_BG_TOKENS[0]).trim()
  return v || (STAGE_BG_FALLBACKS[key] ?? STAGE_BG_FALLBACKS[0])
}
