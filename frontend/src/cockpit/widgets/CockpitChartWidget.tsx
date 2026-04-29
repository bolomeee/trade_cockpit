import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useCockpitStore } from '@/store/cockpitStore'
import { getCockpitChart } from '../lib/api/cockpitChartApi'
import { getCockpitDecision } from '../lib/api/cockpitDecisionApi'

const DEFAULT_MAS = [10, 21, 50, 150, 200]
const DEFAULT_DAYS = 250
const MAS_KEY = DEFAULT_MAS.join(',')

const MA_TOKENS: Record<string, string> = {
  '10': '--color-log-warn',
  '21': '--color-text-muted',
  '50': '--color-signal-neutral',
  '150': '--color-signal-breakout',
  '200': '--color-text-secondary',
}

const MA_FALLBACKS: Record<string, string> = {
  '10': '#f59e0b',
  '21': '#6b7280',
  '50': '#9ca3af',
  '150': '#2962ff',
  '200': '#717182',
}

function readToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

function toTs(date: string): UTCTimestamp {
  return (Date.parse(`${date}T00:00:00Z`) / 1000) as UTCTimestamp
}

export function CockpitChartWidget() {
  const ticker = useCockpitStore((s) => s.selectedTicker)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const priceLinesRef = useRef<IPriceLine[]>([])

  const chartQuery = useQuery({
    queryKey: ['cockpit-chart', ticker, MAS_KEY, DEFAULT_DAYS],
    queryFn: () => getCockpitChart(ticker!, { mas: DEFAULT_MAS, days: DEFAULT_DAYS }),
    enabled: ticker != null,
    staleTime: 5 * 60 * 1000,
  })

  const decisionQuery = useQuery({
    queryKey: ['cockpit-decision', ticker],
    queryFn: () => getCockpitDecision(ticker!),
    enabled: ticker != null,
    staleTime: 60 * 1000,
    retry: false,
  })

  // Chart creation: rebuild when chart data changes (ticker switch destroys + recreates)
  useEffect(() => {
    const container = containerRef.current
    if (!container || !chartQuery.data) return

    const cd = chartQuery.data
    const upColor = readToken('--color-change-positive', '#10b981')
    const downColor = readToken('--color-change-negative', '#ef4444')
    const textColor = readToken('--color-text-secondary', '#717182')
    const borderColor = readToken('--color-border', 'rgba(0,0,0,0.1)')
    const bgColor = readToken('--color-card', '#ffffff')

    const chart: IChartApi = createChart(container, {
      width: container.clientWidth || 1,
      height: container.clientHeight || 1,
      layout: { background: { color: bgColor }, textColor, fontSize: 12 },
      grid: { vertLines: { color: borderColor }, horzLines: { color: borderColor } },
      rightPriceScale: { borderColor },
      timeScale: { borderColor, timeVisible: false },
      crosshair: { mode: 1 },
    })

    const candleSeries: ISeriesApi<'Candlestick'> = chart.addSeries(CandlestickSeries, {
      upColor,
      downColor,
      wickUpColor: upColor,
      wickDownColor: downColor,
      borderVisible: false,
    })
    candleSeries.setData(
      cd.bars.map((b) => ({
        time: toTs(b.date),
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    )
    candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.25 } })
    candleSeriesRef.current = candleSeries

    const volUp = `${upColor}66`
    const volDown = `${downColor}66`
    const volumeSeries: ISeriesApi<'Histogram'> = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      priceLineVisible: false,
      lastValueVisible: false,
    })
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })
    volumeSeries.setData(
      cd.bars.map((b) => ({
        time: toTs(b.date),
        value: b.volume,
        color: b.close >= b.open ? volUp : volDown,
      })),
    )

    for (const period of DEFAULT_MAS) {
      const key = String(period)
      const points = cd.mas[key]
      if (!points || points.length === 0) continue
      const maSeries: ISeriesApi<'Line'> = chart.addSeries(LineSeries, {
        color: readToken(MA_TOKENS[key], MA_FALLBACKS[key]),
        lineWidth: period === 150 ? 2 : 1,
        priceLineVisible: false,
        lastValueVisible: false,
      })
      maSeries.setData(points.map((p) => ({ time: toTs(p.date), value: p.value })))
    }

    if (cd.avwap.anchor && cd.avwap.series.length > 0) {
      const avwapSeries: ISeriesApi<'Line'> = chart.addSeries(LineSeries, {
        color: readToken('--color-chart-avwap', '#a855f7'),
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      })
      avwapSeries.setData(cd.avwap.series.map((p) => ({ time: toTs(p.date), value: p.value })))
    }

    chart.timeScale().fitContent()

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0) {
          chart.applyOptions({ width: Math.floor(width), height: Math.floor(height) })
        }
      }
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
      candleSeriesRef.current = null
      priceLinesRef.current = []
      chart.remove()
    }
  }, [chartQuery.data])

  // Decision price lines: applies after chart exists; removes stale lines before adding
  useEffect(() => {
    const series = candleSeriesRef.current
    if (!series) return

    for (const line of priceLinesRef.current) {
      series.removePriceLine(line)
    }
    priceLinesRef.current = []

    if (!decisionQuery.data) return

    const d = decisionQuery.data
    const entryColor = readToken('--color-chart-entry', '#10b981')
    const stopColor = readToken('--color-chart-stop', '#ef4444')
    const targetColor = readToken('--color-chart-target', '#2962ff')

    priceLinesRef.current = [
      series.createPriceLine({
        price: d.entryPrice,
        color: entryColor,
        lineWidth: 1,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: '',
      }),
      series.createPriceLine({
        price: d.stopPrice,
        color: stopColor,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: '',
      }),
      series.createPriceLine({
        price: d.target2r,
        color: targetColor,
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        title: '',
      }),
      series.createPriceLine({
        price: d.target3r,
        color: targetColor,
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        title: '',
      }),
    ]
  }, [decisionQuery.data, chartQuery.data])

  if (!ticker) {
    return (
      <div
        style={{
          display: 'flex',
          height: '100%',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--color-text-muted)',
          fontSize: 'var(--font-size-body)',
        }}
      >
        请从 Setup Monitor 选择一只股票
      </div>
    )
  }

  const decision = decisionQuery.data
  const headerText = decision
    ? `${ticker} · ${decision.setupType} · ${decision.setupQuality ?? '—'}`
    : ticker

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div
        style={{
          padding: '8px 12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <span
          style={{
            fontWeight: 'var(--font-weight-medium)',
            fontSize: 'var(--font-size-body)',
            color: 'var(--color-text-primary)',
          }}
        >
          {headerText}
        </span>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          {DEFAULT_MAS.map((period) => (
            <span key={period} style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: '12px',
                  height: '2px',
                  background: `var(${MA_TOKENS[String(period)]}, ${MA_FALLBACKS[String(period)]})`,
                }}
              />
              <span
                style={{ fontSize: 'var(--font-size-badge)', color: 'var(--color-text-secondary)' }}
              >
                MA{period}
              </span>
            </span>
          ))}
          {chartQuery.data?.avwap.anchor && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: '12px',
                  height: '2px',
                  background: 'var(--color-chart-avwap, #a855f7)',
                }}
              />
              <span
                style={{ fontSize: 'var(--font-size-badge)', color: 'var(--color-text-secondary)' }}
              >
                AVWAP
              </span>
            </span>
          )}
        </div>
      </div>

      {chartQuery.isPending && (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-text-muted)',
          }}
        >
          Loading chart…
        </div>
      )}

      {chartQuery.isError && (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-change-negative)',
          }}
        >
          Failed to load chart data
        </div>
      )}

      {chartQuery.isSuccess && (
        <div
          ref={containerRef}
          data-testid="cockpit-chart-container"
          style={{ flex: 1, overflow: 'hidden' }}
        />
      )}
    </div>
  )
}
