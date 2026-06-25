import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useCockpitStore } from '@/store/cockpitStore'
import { useThemeStore } from '@/store/useThemeStore'
import { readCssColor as readToken } from '@/lib/cssColor'
import { getCockpitWeeklyChart } from '../lib/api/cockpitWeeklyChartApi'
import { STAGE_LABELS, STAGE_BG_TOKENS, STAGE_BG_FALLBACKS } from '../lib/weeklyStageTokens'

const WEEKLY_MAS = [10, 30, 40] as const
const DEFAULT_WEEKS = 50

const MA_TOKENS: Record<string, string> = {
  '10': '--color-log-warn',
  '30': '--color-signal-breakout',
  '40': '--color-text-secondary',
}

const MA_FALLBACKS: Record<string, string> = {
  '10': '#f59e0b',
  '30': '#2962ff',
  '40': '#717182',
}

function toTs(date: string): UTCTimestamp {
  return (Date.parse(`${date}T00:00:00Z`) / 1000) as UTCTimestamp
}

export function WeeklyStageChartWidget() {
  const ticker = useCockpitStore((s) => s.selectedTicker)
  const theme = useThemeStore((s) => s.theme)
  const containerRef = useRef<HTMLDivElement | null>(null)

  const chartQuery = useQuery({
    queryKey: ['cockpit-weekly-chart', ticker, DEFAULT_WEEKS],
    queryFn: () => getCockpitWeeklyChart(ticker!, { weeks: DEFAULT_WEEKS }),
    enabled: ticker != null,
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    const container = containerRef.current
    if (!container || !chartQuery.data) return
    const cd = chartQuery.data
    if (cd.weeklyBars.length === 0) return

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
      cd.weeklyBars.map((b) => ({
        time: toTs(b.date),
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    )
    candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.25 } })

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
      cd.weeklyBars.map((b) => ({
        time: toTs(b.date),
        value: b.volume,
        color: b.close >= b.open ? volUp : volDown,
      })),
    )

    for (const period of WEEKLY_MAS) {
      const key = String(period)
      const points = cd.weeklyMas[key]
      if (!points || points.length === 0) continue
      const maSeries: ISeriesApi<'Line'> = chart.addSeries(LineSeries, {
        color: readToken(MA_TOKENS[key], MA_FALLBACKS[key]),
        lineWidth: period === 30 ? 2 : 1,
        priceLineVisible: false,
        lastValueVisible: false,
      })
      maSeries.setData(points.map((p) => ({ time: toTs(p.date), value: p.value })))
    }

    const lastDate = cd.weeklyBars[cd.weeklyBars.length - 1].date
    const from = new Date(`${lastDate}T00:00:00Z`)
    from.setFullYear(from.getFullYear() - 1)
    chart.timeScale().setVisibleRange({
      from: (from.getTime() / 1000) as UTCTimestamp,
      to: toTs(lastDate),
    })

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
      chart.remove()
    }
    // theme: rebuild so layout/series colors re-read the (now dark) tokens
  }, [chartQuery.data, theme])

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

  const stagePayload = chartQuery.data?.stage
  const stageNum = stagePayload?.stage ?? 0
  const stageColor = readToken(STAGE_BG_TOKENS[stageNum], STAGE_BG_FALLBACKS[stageNum])
  const stageLabel = STAGE_LABELS[stageNum] ?? 'Unknown'
  const headerText = stagePayload
    ? `${ticker} · Stage ${stageNum} · ${stageLabel}`
    : ticker

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div
        data-testid="weekly-stage-header"
        data-stage={stageNum}
        style={{
          padding: '8px 12px',
          background: stageColor,
          color: '#ffffff',
          fontWeight: 'var(--font-weight-medium)',
          fontSize: 'var(--font-size-body)',
          flexShrink: 0,
        }}
      >
        {headerText}
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

      {chartQuery.isSuccess && chartQuery.data.weeklyBars.length === 0 && (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-text-muted)',
          }}
        >
          数据不足
        </div>
      )}

      {chartQuery.isSuccess && chartQuery.data.weeklyBars.length > 0 && (
        <div
          ref={containerRef}
          data-testid="weekly-chart-container"
          style={{ flex: 1, overflow: 'hidden' }}
        />
      )}
    </div>
  )
}
