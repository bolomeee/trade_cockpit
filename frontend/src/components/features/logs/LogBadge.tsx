import type { LogLevel } from '@/types/log'

interface LogBadgeProps {
  level: LogLevel
}

const BASE_STYLE: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: '52px',
  padding: '2px 10px',
  borderRadius: '9999px',
  fontSize: 'var(--font-size-caption)',
  fontWeight: 'var(--font-weight-medium)',
  lineHeight: 1.4,
  border: '1px solid transparent',
}

function styleFor(level: LogLevel): React.CSSProperties {
  switch (level) {
    case 'OK':
      return { background: 'var(--color-log-ok)', color: '#fff' }
    case 'INFO':
      return { background: 'var(--color-log-info)', color: '#fff' }
    case 'ERROR':
      return { background: 'var(--color-log-error)', color: '#fff' }
    case 'WARN':
      return {
        background: '#fff',
        color: 'var(--color-log-warn)',
        borderColor: 'var(--color-log-warn)',
      }
  }
}

export function LogBadge({ level }: LogBadgeProps) {
  return <span style={{ ...BASE_STYLE, ...styleFor(level) }}>{level}</span>
}
