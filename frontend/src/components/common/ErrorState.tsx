interface ErrorStateProps {
  title?: string
  onRetry: () => void
}

export function ErrorState({ title = '数据加载失败', onRetry }: ErrorStateProps) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 24px' }}>
      <p style={{ fontSize: 'var(--font-size-body)', color: 'var(--color-error)' }}>
        {title}
      </p>
      <button
        onClick={onRetry}
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
        重试
      </button>
    </div>
  )
}
