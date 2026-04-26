import { RotateCcw } from 'lucide-react'

import { Button } from '@/components/ui/button'

import { getCockpitDefaultLayout } from './CockpitRegistry'
import { useCockpitLayoutStore } from './useCockpitLayoutStore'

export function CockpitResetLayoutButton() {
  const reset = useCockpitLayoutStore((s) => s.reset)

  return (
    <Button variant="outline" size="sm" onClick={() => reset(getCockpitDefaultLayout())}>
      <RotateCcw />
      Reset
    </Button>
  )
}
