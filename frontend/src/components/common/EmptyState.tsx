interface EmptyStateProps {
  title: string
  description?: string
  action?: { label: string; onClick: () => void }
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 24px' }}>
      <p style={{ fontSize: 'var(--font-size-body)', fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-secondary)' }}>
        {title}
      </p>
      {description && (
        <p style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)', marginTop: '8px' }}>
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          style={{
            marginTop: '16px',
            padding: '6px 16px',
            borderRadius: 'var(--radius-button)',
            border: '1px solid var(--color-border)',
            background: 'transparent',
            fontSize: 'var(--font-size-body)',
            cursor: 'pointer',
            color: 'var(--color-text-primary)',
          }}
        >
          {action.label}
        </button>
      )}
    </div>
  )
}
