import { RotateCcw } from 'lucide-react'

import { Button } from '@/components/ui/button'

import { getWorkbenchDefaultLayout } from './WidgetRegistry'
import { useLayoutStore } from './useLayoutStore'

export function ResetLayoutButton() {
  const reset = useLayoutStore((s) => s.reset)

  return (
    <Button variant="outline" size="sm" onClick={() => reset(getWorkbenchDefaultLayout())}>
      <RotateCcw />
      Reset
    </Button>
  )
}
