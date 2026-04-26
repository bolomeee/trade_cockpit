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
import {
  createPendingOrder,
  updatePendingOrder,
  type PendingOrder,
  type PendingOrderInput,
  type PendingOrderPatch,
} from '../lib/api/cockpitPendingOrdersApi'
import {
  newOrderSchema,
  editOrderSchema,
  setupTypeOptions,
  type NewOrderFormValues,
  type EditOrderFormValues,
} from './_pendingOrderFormSchemas'

// ── styles ────────────────────────────────────────────────────────────────────

const fieldStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: '4px' }
const errorStyle: React.CSSProperties = {
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-signal-danger)',
  marginTop: '2px',
}

// ── props ─────────────────────────────────────────────────────────────────────

type Props =
  | { mode: 'new'; open: boolean; onClose: () => void; onSaved: () => void; initialOrder?: never }
  | { mode: 'edit'; open: boolean; onClose: () => void; onSaved: () => void; initialOrder: PendingOrder }

// ── new form ──────────────────────────────────────────────────────────────────

function NewOrderForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const queryClient = useQueryClient()

  const form = useForm<NewOrderFormValues>({
    resolver: zodResolver(newOrderSchema),
    defaultValues: {
      ticker: '',
      setupType: '',
      entryPrice: undefined,
      stopPrice: undefined,
      shares: undefined,
      target2r: undefined,
      target3r: undefined,
      expirationDate: '',
      notes: '',
    },
  })

  const mutation = useMutation({
    mutationFn: (data: NewOrderFormValues) => {
      const input: PendingOrderInput = {
        ticker: data.ticker.toUpperCase(),
        setupType: data.setupType,
        entryPrice: data.entryPrice,
        stopPrice: data.stopPrice,
        shares: data.shares,
        ...(data.target2r != null && { target2r: data.target2r }),
        ...(data.target3r != null && { target3r: data.target3r }),
        ...(data.expirationDate ? { expirationDate: data.expirationDate } : {}),
        ...(data.notes ? { notes: data.notes } : {}),
      }
      return createPendingOrder(input)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cockpit-pending-orders'] })
      onSaved()
    },
  })

  const { errors } = form.formState

  return (
    <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '4px 0' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pod-ticker">Ticker</Label>
            <Input id="pod-ticker" placeholder="NVDA" {...form.register('ticker')} />
            {errors.ticker && <span style={errorStyle}>{errors.ticker.message}</span>}
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pod-setup">Setup type</Label>
            <Controller
              control={form.control}
              name="setupType"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="pod-setup">
                    <SelectValue placeholder="Select…" />
                  </SelectTrigger>
                  <SelectContent>
                    {setupTypeOptions.map((o) => (
                      <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.setupType && <span style={errorStyle}>{errors.setupType.message}</span>}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pod-entry">Entry price</Label>
            <Input id="pod-entry" type="number" step="any"
              {...form.register('entryPrice', { setValueAs: (v: string) => v === '' ? undefined : Number(v) })} />
            {errors.entryPrice && <span style={errorStyle}>{errors.entryPrice.message}</span>}
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pod-stop">Stop price</Label>
            <Input id="pod-stop" type="number" step="any"
              {...form.register('stopPrice', { setValueAs: (v: string) => v === '' ? undefined : Number(v) })} />
            {errors.stopPrice && <span style={errorStyle}>{errors.stopPrice.message}</span>}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pod-shares">Shares</Label>
            <Input id="pod-shares" type="number" step="1"
              {...form.register('shares', { setValueAs: (v: string) => v === '' ? undefined : Number(v) })} />
            {errors.shares && <span style={errorStyle}>{errors.shares.message}</span>}
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pod-exp">Expiration date (optional)</Label>
            <Input id="pod-exp" type="date" {...form.register('expirationDate')} />
            {errors.expirationDate && <span style={errorStyle}>{errors.expirationDate.message}</span>}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pod-t2r">Target 2R (optional)</Label>
            <Input id="pod-t2r" type="number" step="any"
              {...form.register('target2r', { setValueAs: (v: string) => (v === '' || v == null) ? undefined : Number(v) })} />
            {errors.target2r && <span style={errorStyle}>{errors.target2r.message}</span>}
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pod-t3r">Target 3R (optional)</Label>
            <Input id="pod-t3r" type="number" step="any"
              {...form.register('target3r', { setValueAs: (v: string) => (v === '' || v == null) ? undefined : Number(v) })} />
            {errors.target3r && <span style={errorStyle}>{errors.target3r.message}</span>}
          </div>
        </div>

        <div style={fieldStyle}>
          <Label htmlFor="pod-notes">Notes (optional)</Label>
          <Input id="pod-notes" {...form.register('notes')} />
        </div>

        {mutation.isError && (
          <p style={{ ...errorStyle, marginTop: 0 }}>提交失败，请重试</p>
        )}
      </div>

      <DialogFooter style={{ marginTop: '8px' }}>
        <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Saving…' : 'Add Order'}
        </Button>
      </DialogFooter>
    </form>
  )
}

// ── edit form ─────────────────────────────────────────────────────────────────

function EditOrderForm({
  order,
  onClose,
  onSaved,
}: {
  order: PendingOrder
  onClose: () => void
  onSaved: () => void
}) {
  const queryClient = useQueryClient()

  const form = useForm<EditOrderFormValues>({
    resolver: zodResolver(editOrderSchema),
    defaultValues: {
      ticker: order.ticker,
      setupType: order.setupType ?? '',
      entryPrice: order.entryPrice,
      stopPrice: order.stopPrice,
      shares: order.shares,
      target2r: order.target2r ?? undefined,
      target3r: order.target3r ?? undefined,
      expirationDate: order.expirationDate ?? '',
      notes: order.notes ?? '',
    },
  })

  const mutation = useMutation({
    mutationFn: (patch: PendingOrderPatch) => updatePendingOrder(order.id, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cockpit-pending-orders'] })
      onSaved()
    },
  })

  // Subscribe to dirtyFields during render — react-hook-form uses lazy subscription;
  // without this, dirtyFields won't be tracked when read in handleSubmit.
  const { errors, dirtyFields } = form.formState

  function handleSubmit(data: EditOrderFormValues) {
    const patch: PendingOrderPatch = {}
    if (dirtyFields.ticker) patch.ticker = data.ticker.toUpperCase()
    if (dirtyFields.setupType) patch.setupType = data.setupType
    if (dirtyFields.entryPrice) patch.entryPrice = data.entryPrice
    if (dirtyFields.stopPrice) patch.stopPrice = data.stopPrice
    if (dirtyFields.shares) patch.shares = data.shares
    if (dirtyFields.target2r) patch.target2r = data.target2r
    if (dirtyFields.target3r) patch.target3r = data.target3r
    if (dirtyFields.expirationDate) patch.expirationDate = data.expirationDate || undefined
    if (dirtyFields.notes) patch.notes = data.notes
    mutation.mutate(patch)
  }

  return (
    <form onSubmit={form.handleSubmit(handleSubmit)}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '4px 0' }}>
        <div style={{ fontSize: 'var(--font-size-caption)', color: 'var(--color-text-secondary)' }}>
          {order.ticker} · Entry {order.entryPrice} · {order.shares} sh
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pod-edit-ticker">Ticker</Label>
            <Input id="pod-edit-ticker" {...form.register('ticker')} />
            {errors.ticker && <span style={errorStyle}>{errors.ticker.message}</span>}
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pod-edit-setup">Setup type</Label>
            <Controller
              control={form.control}
              name="setupType"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="pod-edit-setup">
                    <SelectValue placeholder="Select…" />
                  </SelectTrigger>
                  <SelectContent>
                    {setupTypeOptions.map((o) => (
                      <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.setupType && <span style={errorStyle}>{errors.setupType.message}</span>}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pod-edit-entry">Entry price</Label>
            <Input id="pod-edit-entry" type="number" step="any"
              {...form.register('entryPrice', { setValueAs: (v: string) => v === '' ? undefined : Number(v) })} />
            {errors.entryPrice && <span style={errorStyle}>{errors.entryPrice.message}</span>}
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pod-edit-stop">Stop price</Label>
            <Input id="pod-edit-stop" type="number" step="any"
              {...form.register('stopPrice', { setValueAs: (v: string) => v === '' ? undefined : Number(v) })} />
            {errors.stopPrice && <span style={errorStyle}>{errors.stopPrice.message}</span>}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pod-edit-shares">Shares</Label>
            <Input id="pod-edit-shares" type="number" step="1"
              {...form.register('shares', { setValueAs: (v: string) => v === '' ? undefined : Number(v) })} />
            {errors.shares && <span style={errorStyle}>{errors.shares.message}</span>}
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pod-edit-exp">Expiration date (optional)</Label>
            <Input id="pod-edit-exp" type="date" {...form.register('expirationDate')} />
            {errors.expirationDate && <span style={errorStyle}>{errors.expirationDate.message}</span>}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={fieldStyle}>
            <Label htmlFor="pod-edit-t2r">Target 2R (optional)</Label>
            <Input id="pod-edit-t2r" type="number" step="any"
              {...form.register('target2r', { setValueAs: (v: string) => (v === '' || v == null) ? undefined : Number(v) })} />
            {errors.target2r && <span style={errorStyle}>{errors.target2r.message}</span>}
          </div>
          <div style={fieldStyle}>
            <Label htmlFor="pod-edit-t3r">Target 3R (optional)</Label>
            <Input id="pod-edit-t3r" type="number" step="any"
              {...form.register('target3r', { setValueAs: (v: string) => (v === '' || v == null) ? undefined : Number(v) })} />
            {errors.target3r && <span style={errorStyle}>{errors.target3r.message}</span>}
          </div>
        </div>

        <div style={fieldStyle}>
          <Label htmlFor="pod-edit-notes">Notes (optional)</Label>
          <Input id="pod-edit-notes" {...form.register('notes')} />
        </div>

        {mutation.isError && (
          <p style={{ ...errorStyle, marginTop: 0 }}>更新失败，请重试</p>
        )}
      </div>

      <DialogFooter style={{ marginTop: '8px' }}>
        <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Saving…' : 'Save'}
        </Button>
      </DialogFooter>
    </form>
  )
}

// ── wrapper ───────────────────────────────────────────────────────────────────

export function PendingOrderFormDialog({ mode, open, onClose, onSaved, initialOrder }: Props) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent showCloseButton>
        <DialogHeader>
          <DialogTitle>{mode === 'new' ? 'New Pending Order' : 'Edit Pending Order'}</DialogTitle>
        </DialogHeader>
        {mode === 'new' ? (
          <NewOrderForm onClose={onClose} onSaved={onSaved} />
        ) : (
          <EditOrderForm order={initialOrder} onClose={onClose} onSaved={onSaved} />
        )}
      </DialogContent>
    </Dialog>
  )
}
