import type { Fundamentals } from '@/types/stockDetail'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/common/ErrorState'
import { formatPercent } from '@/lib/format'
import {
  Table,
  TableBody,
  TableCell,
  TableRow,
} from '@/components/ui/table'

interface FundamentalsCardProps {
  fundamentals: Fundamentals | undefined
  loading: boolean
  error: boolean
  onRetry: () => void
}

type Metric = { label: string; value: string | null }

function formatCurrency(value: number | null | undefined): string | null {
  if (value == null) return null
  if (Math.abs(value) >= 1_000_000_000) {
    return `$${(value / 1_000_000_000).toFixed(2)}B`
  }
  if (Math.abs(value) >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(2)}M`
  }
  return `$${value.toFixed(2)}`
}

function formatRatio(v: number | null | undefined): string | null {
  return v == null ? null : v.toFixed(2)
}

function formatShares(v: number | null | undefined): string | null {
  if (v == null) return null
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)}B`
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`
  return v.toLocaleString()
}

function buildMetrics(f: Fundamentals | undefined): { left: Metric[]; right: Metric[] } {
  const roce = f?.roce
  return {
    left: [
      { label: 'P/E', value: formatRatio(f?.priceToEarnings) },
      { label: 'P/S', value: formatRatio(f?.priceToSales) },
      { label: 'PEG', value: formatRatio(f?.peg) },
      { label: 'ROCE', value: roce == null ? null : formatPercent(roce * 100) },
    ],
    right: [
      { label: 'FCF', value: f ? formatCurrency(f.freeCashFlow) : null },
      { label: 'P/FCF', value: formatRatio(f?.pFcfRaw) },
      { label: 'P/FCF(−SBC)', value: formatRatio(f?.pFcfAdj) },
      { label: 'Float', value: formatShares(f?.sharesFloat) },
    ],
  }
}

function MetricsTable({ rows, loading }: { rows: Metric[]; loading: boolean }) {
  return (
    <Table>
      <TableBody>
        {rows.map((m) => (
          <TableRow key={m.label}>
            <TableCell className="text-muted-foreground">{m.label}</TableCell>
            <TableCell
              className="text-right"
              style={{
                fontFamily: 'var(--font-family-numeric)',
                fontWeight: 'var(--font-weight-bold)',
              }}
            >
              {loading ? (
                <Skeleton style={{ height: '16px', width: '48px', marginLeft: 'auto' }} />
              ) : (
                m.value ?? '—'
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function FundamentalsCard({
  fundamentals,
  loading,
  error,
  onRetry,
}: FundamentalsCardProps) {
  if (error) return <ErrorState title="基本面加载失败" onRetry={onRetry} />

  const { left, right } = buildMetrics(fundamentals)

  return (
    <div className="grid grid-cols-2 gap-4">
      <MetricsTable rows={left} loading={loading || !fundamentals} />
      <MetricsTable rows={right} loading={loading || !fundamentals} />
    </div>
  )
}
