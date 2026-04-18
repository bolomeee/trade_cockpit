import type { LogEntry } from '@/types/log'
import { LogBadge } from './LogBadge'

interface LogsTableProps {
  logs: LogEntry[]
}

const CELL_BASE: React.CSSProperties = {
  padding: '12px 16px',
  fontSize: 'var(--font-size-body)',
  color: 'var(--color-text-primary)',
  textAlign: 'left',
  verticalAlign: 'middle',
}

const HEAD_CELL: React.CSSProperties = {
  ...CELL_BASE,
  fontSize: 'var(--font-size-caption)',
  fontWeight: 'var(--font-weight-medium)',
  color: 'var(--color-text-secondary)',
  borderBottom: '1px solid var(--color-border)',
  background: 'var(--color-card)',
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function LogsTable({ logs }: LogsTableProps) {
  return (
    <div
      style={{
        background: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-card)',
        overflow: 'hidden',
      }}
    >
      <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
        <colgroup>
          <col style={{ width: '200px' }} />
          <col style={{ width: '88px' }} />
          <col style={{ width: '160px' }} />
          <col />
        </colgroup>
        <thead>
          <tr>
            <th style={HEAD_CELL}>Timestamp</th>
            <th style={HEAD_CELL}>Level</th>
            <th style={HEAD_CELL}>Source</th>
            <th style={HEAD_CELL}>Message</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log, idx) => (
            <tr
              key={log.id}
              style={{
                borderTop: idx === 0 ? 'none' : '1px solid var(--color-border)',
              }}
            >
              <td style={{ ...CELL_BASE, fontFamily: 'var(--font-family-mono)', whiteSpace: 'nowrap' }}>
                {formatTimestamp(log.createdAt)}
              </td>
              <td style={CELL_BASE}>
                <LogBadge level={log.level} />
              </td>
              <td style={{ ...CELL_BASE, color: 'var(--color-text-secondary)' }}>
                {log.source}
              </td>
              <td
                style={{
                  ...CELL_BASE,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
                title={log.message}
              >
                {log.message}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
