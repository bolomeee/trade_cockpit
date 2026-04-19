import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { createJournal } from '@/lib/api/journal'
import { ApiError } from '@/lib/api/client'
import { ACTIONS, type Action } from '@/types/journal'

const DEFAULT_ACTION: Action = 'BUY'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

const labelStyle: React.CSSProperties = {
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-text-secondary)',
  marginBottom: '4px',
}

export function JournalQuickAddCard() {
  const queryClient = useQueryClient()
  const [ticker, setTicker] = useState('')
  const [action, setAction] = useState<Action>(DEFAULT_ACTION)
  const [price, setPrice] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: createJournal,
    onMutate: () => setFormError(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['journal'] })
      setTicker('')
      setAction(DEFAULT_ACTION)
      setPrice('')
    },
    onError: (err) => {
      const message =
        err instanceof ApiError ? err.message : '添加失败，请重试'
      setFormError(message)
    },
  })

  const priceNum = Number(price)
  const canSubmit =
    ticker.trim().length > 0 &&
    price.trim().length > 0 &&
    Number.isFinite(priceNum) &&
    priceNum > 0 &&
    !mutation.isPending

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    mutation.mutate({
      ticker: ticker.trim().toUpperCase(),
      action,
      price: priceNum,
      date: todayIso(),
      positionSize: null,
      stopLoss: null,
      targetPrice: null,
      reason: null,
      reference: null,
    })
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
      <div>
        <Label htmlFor="quick-ticker" style={labelStyle}>Ticker</Label>
        <Input
          id="quick-ticker"
          value={ticker}
          placeholder="e.g. AAPL"
          onChange={(e) => setTicker(e.target.value)}
          autoComplete="off"
        />
      </div>

      <div>
        <Label htmlFor="quick-action" style={labelStyle}>Action</Label>
        <Select value={action} onValueChange={(v) => setAction(v as Action)}>
          <SelectTrigger id="quick-action">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ACTIONS.map((a) => (
              <SelectItem key={a} value={a}>{a}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label htmlFor="quick-price" style={labelStyle}>Price</Label>
        <Input
          id="quick-price"
          type="number"
          inputMode="decimal"
          step="0.01"
          min="0"
          value={price}
          placeholder="0.00"
          onChange={(e) => setPrice(e.target.value)}
        />
      </div>

      {formError && (
        <div style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-error)' }}>
          {formError}
        </div>
      )}

      <Button type="submit" disabled={!canSubmit} style={{ width: '100%' }}>
        {mutation.isPending ? 'Adding…' : '+ Add Entry'}
      </Button>
    </form>
  )
}
