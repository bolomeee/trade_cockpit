import { useEffect, useRef } from 'react'
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { ChartData } from '@/types/stockDetail'

interface PriceChartProps {
  data: ChartData
  height?: number
}

function toUtcTimestamp(dateStr: string): UTCTimestamp {
  return (Date.parse(`${dateStr}T00:00:00Z`) / 1000) as UTCTimestamp
}

function readToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim()
  return v || fallback
}

export function PriceChart({ data, height = 302 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const upColor = readToken('--color-change-positive', '#10b981')
    const downColor = readToken('--color-change-negative', '#ef4444')
    const maColor = readToken('--color-signal-breakout', '#2962ff')
    const markerColor = readToken('--color-signal-buyzone', '#10b981')
    const textColor = readToken('--color-text-secondary', '#717182')
    const borderColor = readToken('--color-border', 'rgba(0,0,0,0.1)')
    const bgColor = readToken('--color-card', '#ffffff')

    const chart: IChartApi = createChart(container, {
      width: container.clientWidth,
      height,
      layout: {
        background: { color: bgColor },
        textColor,
      },
      grid: {
        vertLines: { color: borderColor },
        horzLines: { color: borderColor },
      },
      rightPriceScale: { borderColor },
      timeScale: { borderColor, timeVisible: false },
      crosshair: { mode: 1 },
    })

    const candleSeries: ISeriesApi<'Candlestick'> = chart.addSeries(
      CandlestickSeries,
      {
        upColor,
        downColor,
        wickUpColor: upColor,
        wickDownColor: downColor,
        borderVisible: false,
      }
    )

    candleSeries.setData(
      data.bars.map((b) => ({
        time: toUtcTimestamp(b.date),
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }))
    )

    if (data.ma150.length > 0) {
      const maSeries: ISeriesApi<'Line'> = chart.addSeries(LineSeries, {
        color: maColor,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      })
      maSeries.setData(
        data.ma150.map((p) => ({
          time: toUtcTimestamp(p.date),
          value: p.value,
        }))
      )
    }

    if (data.pullbackMarkers.length > 0) {
      const markers: SeriesMarker<Time>[] = data.pullbackMarkers.map((m) => ({
        time: toUtcTimestamp(m.date),
        position: 'belowBar',
        color: markerColor,
        shape: 'arrowUp',
      }))
      createSeriesMarkers(candleSeries, markers)
    }

    chart.timeScale().fitContent()

    const handleResize = () => {
      if (container) chart.applyOptions({ width: container.clientWidth })
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [data, height])

  return (
    <div
      ref={containerRef}
      data-testid="price-chart"
      style={{
        width: '100%',
        height: `${height}px`,
        borderRadius: 'var(--radius-card)',
        overflow: 'hidden',
      }}
    />
  )
}
