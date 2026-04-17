import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { JournalEntryForm, type JournalFormValues } from './JournalEntryForm'
import { createJournal, updateJournal } from '@/lib/api/journal'
import { ApiError } from '@/lib/api/client'
import type { JournalEntry } from '@/types/journal'

type Mode = 'new' | 'edit'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: Mode
  entry?: JournalEntry | null
}

function toInitialValues(entry?: JournalEntry | null): Partial<JournalFormValues> | undefined {
  if (!entry) return undefined
  return {
    ticker: entry.ticker,
    action: entry.action,
    price: entry.price,
    date: entry.date,
    positionSize: entry.positionSize,
    stopLoss: entry.stopLoss,
    targetPrice: entry.targetPrice,
    reason: entry.reason,
    reference: entry.reference,
  }
}

export function JournalEntryDialog({ open, onOpenChange, mode, entry }: Props) {
  const qc = useQueryClient()
  const [formError, setFormError] = useState<string | null>(null)

  const initialValues = useMemo(() => toInitialValues(entry), [entry])

  const mutation = useMutation({
    mutationFn: (values: JournalFormValues) => {
      const payload = {
        ticker: values.ticker,
        action: values.action,
        price: values.price,
        date: values.date,
        positionSize: values.positionSize,
        stopLoss: values.stopLoss,
        targetPrice: values.targetPrice,
        reason: values.reason,
        reference: values.reference,
      }
      return mode === 'edit' && entry
        ? updateJournal(entry.id, payload)
        : createJournal(payload)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['journal'] })
      onOpenChange(false)
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) setFormError(err.message)
      else setFormError('Unexpected error. Please try again.')
    },
  })

  const handleOpenChange = (next: boolean) => {
    if (!next) setFormError(null)
    onOpenChange(next)
  }

  const handleSubmit = async (values: JournalFormValues) => {
    setFormError(null)
    await mutation.mutateAsync(values).catch(() => {
      /* handled in onError */
    })
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>{mode === 'edit' ? 'Edit Trade Entry' : 'New Trade Entry'}</DialogTitle>
        </DialogHeader>
        <JournalEntryForm
          initialValues={initialValues}
          onSubmit={handleSubmit}
          onCancel={() => handleOpenChange(false)}
          submitLabel={mode === 'edit' ? 'Save Changes' : 'Save Entry'}
          submitting={mutation.isPending}
          formError={formError}
        />
      </DialogContent>
    </Dialog>
  )
}
