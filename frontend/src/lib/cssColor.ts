/**
 * Read a CSS custom property and return a color string safe to hand to
 * lightweight-charts' canvas color parser.
 *
 * That parser (in our version) cannot parse oklch()/oklab()/lab()/lch()/color()
 * — the formats the dark theme resolves to (see tokens-dark.css). This browser
 * also keeps oklch() verbatim in getComputedStyle()/canvas fillStyle, so we
 * rasterize a 1px fill and read the sRGB bytes back to get a real rgb(a) string.
 * Hex/rgb values pass through UNCHANGED so the `${color}66` hex-alpha trick the
 * charts use for volume bars keeps working.
 */
let probeCtx: CanvasRenderingContext2D | null | undefined

export function readCssColor(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  if (!raw) return fallback
  if (!/(oklch|oklab|lab|lch|color)\(/.test(raw)) return raw
  if (probeCtx === undefined) probeCtx = document.createElement('canvas').getContext('2d')
  if (!probeCtx) return fallback
  probeCtx.clearRect(0, 0, 1, 1)
  probeCtx.fillStyle = raw
  probeCtx.fillRect(0, 0, 1, 1)
  const [r, g, b, a] = probeCtx.getImageData(0, 0, 1, 1).data
  return a === 255 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${(a / 255).toFixed(3)})`
}
