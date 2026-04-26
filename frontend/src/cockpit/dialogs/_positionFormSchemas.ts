import { z } from 'zod'

export const newSchema = z
  .object({
    ticker: z.string().min(1, 'Ticker required'),
    entryPrice: z.number({ error: 'Required' }).positive('Must be > 0'),
    entryDate: z.string().min(1, 'Date required'),
    shares: z.number({ error: 'Required' }).int().positive('Must be > 0'),
    stopPrice: z.number({ error: 'Required' }).positive('Must be > 0'),
    target2r: z.number().positive().optional(),
    target3r: z.number().positive().optional(),
    setupType: z.string().optional(),
    notes: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    if (data.entryPrice > 0 && data.stopPrice > 0 && data.entryPrice <= data.stopPrice) {
      ctx.addIssue({ code: 'custom', path: ['entryPrice'], message: 'Entry must be > stop' })
    }
  })

export const editSchema = z.object({
  stopPrice: z.number({ error: 'Required' }).positive('Must be > 0'),
  status: z.enum(['OPEN', 'CLOSED']),
  closedAt: z.string().optional(),
  closePrice: z.number().positive().optional(),
  notes: z.string().optional(),
})

export type NewFormValues = z.infer<typeof newSchema>
export type EditFormValues = z.infer<typeof editSchema>
