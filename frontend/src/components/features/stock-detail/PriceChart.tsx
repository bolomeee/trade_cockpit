import { useEffect, useRef } from 'react'
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { ChartBar, ChartData } from '@/types/stockDetail'

interface PriceChartProps {
  data: ChartData
  onHoverChange?: (bar: ChartBar | null) => void
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

export function PriceChart({ data, onHoverChange }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const onHoverChangeRef = useRef(onHoverChange)
  onHoverChangeRef.current = onHoverChange

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const upColor = readToken('--color-change-positive', '#10b981')
    const downColor = readToken('--color-change-negative', '#ef4444')
    const volumeUp = `${upColor}66`
    const volumeDown = `${downColor}66`
    const maColor = readToken('--color-signal-breakout', '#2962ff')
    const markerColor = readToken('--color-signal-buyzone', '#10b981')
    const textColor = readToken('--color-text-secondary', '#717182')
    const borderColor = readToken('--color-border', 'rgba(0,0,0,0.1)')
    const bgColor = readToken('--color-card', '#ffffff')

    const initialWidth = container.clientWidth || 1
    const initialHeight = container.clientHeight || 1

    const chart: IChartApi = createChart(container, {
      width: initialWidth,
      height: initialHeight,
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

    candleSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.05, bottom: 0.25 },
    })

    const volumeSeries: ISeriesApi<'Histogram'> = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
        priceLineVisible: false,
        lastValueVisible: false,
      },
    )
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })
    volumeSeries.setData(
      data.bars.map((b) => ({
        time: toUtcTimestamp(b.date),
        value: b.volume,
        color: b.close >= b.open ? volumeUp : volumeDown,
      })),
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

    const shortMaData = (window: number, color: string) => {
      const closes = data.bars.map((b) => b.close)
      const points: { time: UTCTimestamp; value: number }[] = []
      let running = 0
      for (let i = 0; i < closes.length; i++) {
        running += closes[i]
        if (i >= window) running -= closes[i - window]
        if (i + 1 >= window) {
          points.push({
            time: toUtcTimestamp(data.bars[i].date),
            value: running / window,
          })
        }
      }
      if (points.length === 0) return
      const series: ISeriesApi<'Line'> = chart.addSeries(LineSeries, {
        color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      })
      series.setData(points)
    }
    shortMaData(5, '#f59e0b')
    shortMaData(20, '#8b5cf6')

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

    const barByTime = new Map<UTCTimestamp, ChartBar>()
    for (const b of data.bars) {
      barByTime.set(toUtcTimestamp(b.date), b)
    }
    const handleCrosshair = (param: { time?: Time; point?: { x: number; y: number } }) => {
      const cb = onHoverChangeRef.current
      if (!cb) return
      if (!param.point || param.time == null) {
        cb(null)
        return
      }
      const bar = barByTime.get(param.time as UTCTimestamp) ?? null
      cb(bar)
    }
    chart.subscribeCrosshairMove(handleCrosshair)

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height: h } = entry.contentRect
        if (width > 0 && h > 0) {
          chart.applyOptions({ width: Math.floor(width), height: Math.floor(h) })
        }
      }
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
      chart.unsubscribeCrosshairMove(handleCrosshair)
      onHoverChangeRef.current?.(null)
      chart.remove()
    }
  }, [data])

  return (
    <div
      ref={containerRef}
      data-testid="price-chart"
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        borderRadius: 'var(--radius-card)',
        overflow: 'hidden',
      }}
    />
  )
}
