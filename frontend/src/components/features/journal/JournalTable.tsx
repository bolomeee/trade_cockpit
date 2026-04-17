import { useState } from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { ActionBadge } from './ActionBadge'
import type { JournalEntry } from '@/types/journal'

interface Props {
  entries: JournalEntry[]
  onEdit?: (entry: JournalEntry) => void
  onDelete: (id: number) => void
}

const cellStyle: React.CSSProperties = {
  padding: '12px 16px',
  borderBottom: '1px solid var(--color-border-subtle)',
  fontSize: 'var(--font-size-body)',
  color: 'var(--color-text-primary)',
  verticalAlign: 'middle',
}

const headerCellStyle: React.CSSProperties = {
  ...cellStyle,
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-text-secondary)',
  fontWeight: 'var(--font-weight-medium)',
  textAlign: 'left',
  background: 'transparent',
}

function formatNum(n: number | null): string {
  return n == null ? '—' : Number.isInteger(n) ? String(n) : n.toFixed(2)
}

interface RowProps {
  entry: JournalEntry
  expanded: boolean
  onToggle: () => void
  onEdit?: (entry: JournalEntry) => void
  onDelete: (id: number) => void
}

function JournalRow({ entry, expanded, onToggle, onEdit, onDelete }: RowProps) {
  const [confirmOpen, setConfirmOpen] = useState(false)

  return (
    <>
      <tr>
        <td style={{ ...cellStyle, width: '32px', paddingRight: 0 }}>
          <button
            type="button"
            aria-label={expanded ? 'Collapse' : 'Expand'}
            onClick={onToggle}
            style={{
              width: '24px',
              height: '24px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: 'var(--color-text-secondary)',
              transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
              transition: 'transform 150ms',
            }}
          >
            ›
          </button>
        </td>
        <td style={cellStyle}>{entry.date}</td>
        <td style={{ ...cellStyle, fontWeight: 'var(--font-weight-bold)' }}>{entry.ticker}</td>
        <td style={cellStyle}>
          <ActionBadge action={entry.action} />
        </td>
        <td style={{ ...cellStyle, textAlign: 'right' }}>${entry.price.toFixed(2)}</td>
        <td style={{ ...cellStyle, textAlign: 'right' }}>{formatNum(entry.positionSize)}</td>
        <td style={{ ...cellStyle, textAlign: 'right', whiteSpace: 'nowrap' }}>
          <button
            type="button"
            aria-label="Edit"
            disabled={!onEdit}
            onClick={() => onEdit?.(entry)}
            style={{
              padding: '4px 8px',
              border: 'none',
              background: 'transparent',
              cursor: onEdit ? 'pointer' : 'not-allowed',
              color: 'var(--color-text-secondary)',
              opacity: onEdit ? 1 : 0.5,
            }}
          >
            ✎
          </button>
          <button
            type="button"
            aria-label="Delete"
            onClick={() => setConfirmOpen(true)}
            style={{
              padding: '4px 8px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: 'var(--color-error)',
            }}
          >
            ✕
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} style={{ ...cellStyle, background: 'var(--color-background)' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: 'var(--spacing-4)',
                fontSize: 'var(--font-size-body)',
                color: 'var(--color-text-primary)',
              }}
            >
              <div>
                <div style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-caption)' }}>
                  Stop Loss
                </div>
                <div>{formatNum(entry.stopLoss)}</div>
              </div>
              <div>
                <div style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-caption)' }}>
                  Target Price
                </div>
                <div>{formatNum(entry.targetPrice)}</div>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <div style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-caption)' }}>
                  Reason
                </div>
                <div>{entry.reason || '—'}</div>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <div style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-caption)' }}>
                  Reference
                </div>
                <div style={{ whiteSpace: 'pre-wrap' }}>{entry.reference || '—'}</div>
              </div>
            </div>
          </td>
        </tr>
      )}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this entry?</AlertDialogTitle>
            <AlertDialogDescription>
              {entry.ticker} · {entry.action} · {entry.date}. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="border-t-0 bg-transparent">
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => onDelete(entry.id)}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export function JournalTable({ entries, onEdit, onDelete }: Props) {
  const [expandedId, setExpandedId] = useState<number | null>(null)

  return (
    <div
      style={{
        background: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-card)',
        overflow: 'hidden',
      }}
    >
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ ...headerCellStyle, width: '32px' }}></th>
            <th style={headerCellStyle}>Date</th>
            <th style={headerCellStyle}>Ticker</th>
            <th style={headerCellStyle}>Action</th>
            <th style={{ ...headerCellStyle, textAlign: 'right' }}>Price</th>
            <th style={{ ...headerCellStyle, textAlign: 'right' }}>Position</th>
            <th style={{ ...headerCellStyle, textAlign: 'right' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <JournalRow
              key={entry.id}
              entry={entry}
              expanded={expandedId === entry.id}
              onToggle={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
              onEdit={onEdit}
              onDelete={onDelete}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
