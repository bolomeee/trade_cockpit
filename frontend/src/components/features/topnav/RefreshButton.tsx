import { RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'

interface RefreshButtonProps {
  isRefreshing: boolean
  onClick: () => void
}

export function RefreshButton({ isRefreshing, onClick }: RefreshButtonProps) {
  return (
    <Button variant="outline" size="sm" onClick={onClick} disabled={isRefreshing}>
      <RefreshCw className={isRefreshing ? 'animate-spin' : undefined} />
      Refresh Data
    </Button>
  )
}
