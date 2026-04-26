import { useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCockpitStore } from '@/store/cockpitStore'
import { createPosition, updatePosition, type Position, type PositionInput, type PositionStatus } from '../lib/api/cockpitPositionsApi'
import type { CockpitDecisionData } from '../lib/api/cockpitDecisionApi'
import { newSchema, editSchema, type NewFormValues, type EditFormValues } from './_positionFormSchemas'

// ── component ─────────────────────────────────────────────────────────────────

type Props =
  | { mode: 'new'; open: boolean; onSaved: () => void; onClose: () => void; initialPosition?: never }
  | { mode: 'edit'; open: boolean; onSaved: () => void; onClose: () => void; initialPosition: Position }

const fieldStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: '4px' }
const errorStyle: React.CSSProperties = {
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-signal-danger)',
  marginTop: '2px',
}
const hintStyle: React.CSSProperties = {
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-text-muted)',
  marginTop: '2px',
}

// ── new mode form ──────────────────────────────────────────────────────────────

function NewPositionForm({
  onSaved,
  onClose,
}: {
  onSaved: () => void
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const selectedTicker = useCockpitStore((s) => s.selectedTicker)

  const queries = queryClient.getQueriesData<CockpitDecisionData>({
    queryKey: selectedTicker ? ['cockpit-decision', selectedTicker] : ['__no_match__'],
  })
  const suggestedShares = queries[0]?.[1]?.suggestedShares ?? null

  const form = useForm<NewFormValues>({
    resolver: zodResolver(newSchema),
    defaultValues: {
      ticker: selectedTicker ?? '',
      entryPrice: undefined,
      entryDate: new Date().toISOString().slice(0, 10),
      shares: undefined,
      stopPrice: undefined,
      target2r: undefined,
      target3r: undefined,
      setupType: '',
      notes: '',
    },
  })

  const mutation = useMutation({
    mutationFn: (data: NewFormValues) => {
      const input: PositionInput = {
        ticker: data.ticker.toUpperCase(),
        entryPrice: data.entryPrice,
        entryDate: data.entryDate,
        shares: data.shares,
        stopPrice: data.stopPrice,
        ...(data.target2r != null && { target2r: data.target2r }),
        ...(data.target3r != null && { target3r: data.target3r }),
        ...(data.setupType ? { setupType: data.setupType } : {}),
        ...(data.notes ? { notes: data.notes } : {}),
      }
      return createPosition(input)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cockpit-positions'] })
      onSaved()
    },
  })

  const { errors } = form.formState

  return (
    <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '4px 0' }}>
        <div style={fieldStyle}>
          <Label htmlFor="pfd-ticker">Ticker</Label>
          <Input
            id="pfd-ticker"
            placeholder="NVDA"
            {...form.register('ticker')}
          />
          {errors.ticker && <span style={errorStyle}>{errors.ticker.message}</span>}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pfd-entry">Entry price</Label>
            <Input
              id="pfd-entry"
              type="number"
              step="any"
              {...form.register('entryPrice', { valueAsNumber: true })}
            />
            {errors.entryPrice && <span style={errorStyle}>{errors.entryPrice.message}</span>}
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pfd-stop">Stop price</Label>
            <Input
              id="pfd-stop"
              type="number"
              step="any"
              {...form.register('stopPrice', { valueAsNumber: true })}
            />
            {errors.stopPrice && <span style={errorStyle}>{errors.stopPrice.message}</span>}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pfd-shares">Shares</Label>
            <Input
              id="pfd-shares"
              type="number"
              step="1"
              {...form.register('shares', { valueAsNumber: true })}
            />
            {errors.shares && <span style={errorStyle}>{errors.shares.message}</span>}
            {suggestedShares != null && selectedTicker && (
              <span style={hintStyle} data-testid="suggested-shares-hint">
                Cockpit 推荐 {suggestedShares} shares
              </span>
            )}
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pfd-date">Entry date</Label>
            <Input
              id="pfd-date"
              type="date"
              {...form.register('entryDate')}
            />
            {errors.entryDate && <span style={errorStyle}>{errors.entryDate.message}</span>}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pfd-t2r">Target 2R (optional)</Label>
            <Input
              id="pfd-t2r"
              type="number"
              step="any"
              {...form.register('target2r', {
                setValueAs: (v: string) => (v === '' || v == null) ? undefined : Number(v),
              })}
            />
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pfd-t3r">Target 3R (optional)</Label>
            <Input
              id="pfd-t3r"
              type="number"
              step="any"
              {...form.register('target3r', {
                setValueAs: (v: string) => (v === '' || v == null) ? undefined : Number(v),
              })}
            />
          </div>
        </div>

        <div style={fieldStyle}>
          <Label htmlFor="pfd-notes">Notes (optional)</Label>
          <Input id="pfd-notes" {...form.register('notes')} />
        </div>

        {mutation.isError && (
          <p style={{ ...errorStyle, marginTop: 0 }}>提交失败，请重试</p>
        )}
      </div>

      <DialogFooter style={{ marginTop: '8px' }}>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Saving…' : 'Add Position'}
        </Button>
      </DialogFooter>
    </form>
  )
}

// ── edit mode form ─────────────────────────────────────────────────────────────

function EditPositionForm({
  position,
  onSaved,
  onClose,
}: {
  position: Position
  onSaved: () => void
  onClose: () => void
}) {
  const queryClient = useQueryClient()

  const [watchStatus, setWatchStatus] = useState<PositionStatus>(position.status)

  const form = useForm<EditFormValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      stopPrice: position.stopPrice,
      status: position.status,
      closedAt: position.closedAt ?? '',
      closePrice: position.closePrice ?? undefined,
      notes: position.notes ?? '',
    },
  })

  const mutation = useMutation({
    mutationFn: (data: EditFormValues) =>
      updatePosition(position.id, {
        stopPrice: data.stopPrice,
        status: data.status,
        ...(data.closedAt ? { closedAt: data.closedAt } : {}),
        ...(data.closePrice != null ? { closePrice: data.closePrice } : {}),
        ...(data.notes ? { notes: data.notes } : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cockpit-positions'] })
      onSaved()
    },
  })

  const { errors } = form.formState

  return (
    <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '4px 0' }}>
        <div style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }}>
          {position.ticker} · Entry {position.entryPrice} · {position.shares} sh
        </div>

        <div style={fieldStyle}>
          <Label htmlFor="pfd-edit-stop">Stop price</Label>
          <Input
            id="pfd-edit-stop"
            type="number"
            step="any"
            {...form.register('stopPrice', { valueAsNumber: true })}
          />
          {errors.stopPrice && <span style={errorStyle}>{errors.stopPrice.message}</span>}
        </div>

        <div style={fieldStyle}>
          <Label htmlFor="pfd-edit-status">Status</Label>
          <Controller
            control={form.control}
            name="status"
            render={({ field }) => (
              <Select value={field.value} onValueChange={(val) => { field.onChange(val); setWatchStatus(val as PositionStatus) }}>
                <SelectTrigger id="pfd-edit-status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="OPEN">OPEN</SelectItem>
                  <SelectItem value="CLOSED">CLOSED</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </div>

        {watchStatus === 'CLOSED' && (
          <>
            <div style={fieldStyle}>
              <Label htmlFor="pfd-edit-closedat">Closed at</Label>
              <Input id="pfd-edit-closedat" type="datetime-local" {...form.register('closedAt')} />
            </div>
            <div style={fieldStyle}>
              <Label htmlFor="pfd-edit-closeprice">Close price</Label>
              <Input
                id="pfd-edit-closeprice"
                type="number"
                step="any"
                {...form.register('closePrice', { valueAsNumber: true })}
              />
            </div>
          </>
        )}

        <div style={fieldStyle}>
          <Label htmlFor="pfd-edit-notes">Notes</Label>
          <Input id="pfd-edit-notes" {...form.register('notes')} />
        </div>

        {mutation.isError && (
          <p style={{ ...errorStyle, marginTop: 0 }}>更新失败，请重试</p>
        )}
      </div>

      <DialogFooter style={{ marginTop: '8px' }}>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Saving…' : 'Save'}
        </Button>
      </DialogFooter>
    </form>
  )
}

// ── wrapper ────────────────────────────────────────────────────────────────────

export function PositionFormDialog({ mode, open, onSaved, onClose, initialPosition }: Props) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent showCloseButton>
        <DialogHeader>
          <DialogTitle>{mode === 'new' ? 'New Position' : 'Edit Position'}</DialogTitle>
        </DialogHeader>
        {mode === 'new' ? (
          <NewPositionForm onSaved={onSaved} onClose={onClose} />
        ) : (
          <EditPositionForm position={initialPosition} onSaved={onSaved} onClose={onClose} />
        )}
      </DialogContent>
    </Dialog>
  )
}
