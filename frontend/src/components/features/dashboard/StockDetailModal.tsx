import type { SignalBoardItem } from '@/types/signal'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { SignalBadge } from './SignalBadge'

interface StockDetailModalProps {
  stock: SignalBoardItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      <span style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }}>{label}</span>
      <span style={{ fontSize: 'var(--font-size-subtitle)', fontWeight: 'var(--font-weight-bold)', fontFamily: 'var(--font-family-numeric)', color: 'var(--color-text-primary)' }}>
        {value}
      </span>
    </div>
  )
}

export function StockDetailModal({ stock, open, onOpenChange }: StockDetailModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[1024px]"
        style={{ backgroundColor: 'var(--color-card)' }}
      >
        {stock ? (
          <>
            <DialogHeader>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)' }}>
                <DialogTitle asChild>
                  <h1 style={{ fontSize: 'var(--font-size-hero)', fontWeight: 'var(--font-weight-bold)', margin: 0 }}>
                    {stock.ticker}
                  </h1>
                </DialogTitle>
                <SignalBadge signalType={stock.signalType} size="md" />
              </div>
              <DialogDescription asChild>
                <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>{stock.name}</p>
              </DialogDescription>
            </DialogHeader>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                gap: 'var(--spacing-4)',
                marginTop: 'var(--spacing-2)',
              }}
            >
              <Metric label="Close Price" value={stock.closePrice !== null ? `$${stock.closePrice.toFixed(2)}` : '—'} />
              <Metric label="MA150" value={stock.ma150Value !== null ? `$${stock.ma150Value.toFixed(2)}` : '—'} />
              <Metric
                label="Distance"
                value={
                  stock.distancePct !== null
                    ? `${stock.distancePct >= 0 ? '+' : ''}${stock.distancePct.toFixed(1)}%`
                    : '—'
                }
              />
              <Metric
                label="Slope"
                value={stock.slopePositive === null ? '—' : stock.slopePositive ? 'UP' : 'DOWN'}
              />
            </div>

            <div
              style={{
                marginTop: 'var(--spacing-4)',
                padding: 'var(--spacing-6)',
                borderRadius: 'var(--radius-card)',
                backgroundColor: 'var(--color-muted)',
                color: 'var(--color-text-secondary)',
                textAlign: 'center',
                fontSize: 'var(--font-size-caption)',
              }}
            >
              Chart, Pullback History, Fundamentals coming in F005
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
