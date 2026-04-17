import { useEffect } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ACTIONS, type Action } from '@/types/journal'

const schema = z.object({
  ticker: z.string().min(1, 'Required').max(10),
  action: z.enum(ACTIONS as [Action, ...Action[]]),
  price: z.number({ message: 'Must be a number' }).positive('Must be > 0'),
  date: z.string().min(1, 'Required'),
  positionSize: z.number().nonnegative('Must be ≥ 0').nullable(),
  stopLoss: z.number().nonnegative('Must be ≥ 0').nullable(),
  targetPrice: z.number().nonnegative('Must be ≥ 0').nullable(),
  reason: z.string().nullable(),
  reference: z.string().nullable(),
})

export type JournalFormValues = z.infer<typeof schema>

const emptyValues: JournalFormValues = {
  ticker: '',
  action: 'BUY',
  price: 0,
  date: new Date().toISOString().slice(0, 10),
  positionSize: null,
  stopLoss: null,
  targetPrice: null,
  reason: null,
  reference: null,
}

interface Props {
  initialValues?: Partial<JournalFormValues>
  onSubmit: (values: JournalFormValues) => Promise<void>
  onCancel: () => void
  submitLabel?: string
  submitting?: boolean
  formError?: string | null
}

const labelStyle: React.CSSProperties = {
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-text-secondary)',
  marginBottom: '4px',
}
const errorStyle: React.CSSProperties = {
  fontSize: 'var(--font-size-caption)',
  color: 'var(--color-error)',
  marginTop: '4px',
}

export function JournalEntryForm({
  initialValues,
  onSubmit,
  onCancel,
  submitLabel = 'Save Entry',
  submitting = false,
  formError = null,
}: Props) {
  const {
    register,
    handleSubmit,
    control,
    watch,
    reset,
    formState: { errors },
  } = useForm<JournalFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { ...emptyValues, ...initialValues },
  })

  useEffect(() => {
    reset({ ...emptyValues, ...initialValues })
  }, [initialValues, reset])

  const action = watch('action')
  const positionDisabled = action === 'WATCH'

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      ...values,
      ticker: values.ticker.trim().toUpperCase(),
      positionSize: positionDisabled ? null : values.positionSize,
    })
  })

  return (
    <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
        <div>
          <Label htmlFor="f-ticker" style={labelStyle}>Ticker *</Label>
          <Input id="f-ticker" placeholder="AAPL" {...register('ticker')} />
          {errors.ticker && <div style={errorStyle}>{errors.ticker.message}</div>}
        </div>
        <div>
          <Label htmlFor="f-date" style={labelStyle}>Date *</Label>
          <Input id="f-date" type="date" {...register('date')} />
          {errors.date && <div style={errorStyle}>{errors.date.message}</div>}
        </div>

        <div>
          <Label htmlFor="f-action" style={labelStyle}>Action *</Label>
          <Controller
            name="action"
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="f-action">
                  <SelectValue placeholder="Select" />
                </SelectTrigger>
                <SelectContent>
                  {ACTIONS.map((a) => (
                    <SelectItem key={a} value={a}>{a}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {errors.action && <div style={errorStyle}>{errors.action.message}</div>}
        </div>
        <div>
          <Label htmlFor="f-price" style={labelStyle}>Price ($) *</Label>
          <Input
            id="f-price"
            type="number"
            step="0.01"
            {...register('price', { valueAsNumber: true })}
          />
          {errors.price && <div style={errorStyle}>{errors.price.message}</div>}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--spacing-4)' }}>
        <div>
          <Label htmlFor="f-position" style={labelStyle}>Position (Shares)</Label>
          <Input
            id="f-position"
            type="number"
            disabled={positionDisabled}
            {...register('positionSize', { setValueAs: (v) => (v === '' || v == null ? null : Number(v)) })}
          />
          {errors.positionSize && <div style={errorStyle}>{errors.positionSize.message}</div>}
        </div>
        <div>
          <Label htmlFor="f-stop" style={labelStyle}>Stop Loss</Label>
          <Input
            id="f-stop"
            type="number"
            step="0.01"
            {...register('stopLoss', { setValueAs: (v) => (v === '' || v == null ? null : Number(v)) })}
          />
          {errors.stopLoss && <div style={errorStyle}>{errors.stopLoss.message}</div>}
        </div>
        <div>
          <Label htmlFor="f-target" style={labelStyle}>Target</Label>
          <Input
            id="f-target"
            type="number"
            step="0.01"
            {...register('targetPrice', { setValueAs: (v) => (v === '' || v == null ? null : Number(v)) })}
          />
          {errors.targetPrice && <div style={errorStyle}>{errors.targetPrice.message}</div>}
        </div>
      </div>

      <div>
        <Label htmlFor="f-reason" style={labelStyle}>Short Reason</Label>
        <Input
          id="f-reason"
          placeholder="e.g. Bounce off 150MA"
          {...register('reason', { setValueAs: (v) => (v ? String(v) : null) })}
        />
      </div>

      <div>
        <Label htmlFor="f-reference" style={labelStyle}>Reference / Notes</Label>
        <Textarea
          id="f-reference"
          rows={4}
          placeholder="Detailed thesis, earnings dates, or market context..."
          {...register('reference', { setValueAs: (v) => (v ? String(v) : null) })}
        />
      </div>

      {formError && (
        <div style={{ ...errorStyle, textAlign: 'right' }}>{formError}</div>
      )}

      <div style={{ display: 'flex', gap: 'var(--spacing-2)', justifyContent: 'flex-end' }}>
        <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </Button>
      </div>
    </form>
  )
}
