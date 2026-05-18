import { z } from 'zod'

// TODO: extract to shared constant when more consumers exist (v1.9+)
export const setupTypeOptions = [
  { value: 'BREAKOUT', label: 'BREAKOUT' },
  { value: 'CAPITULATION', label: 'CAP_REV' },
  { value: 'RECLAIM', label: 'RECLAIM' },
  { value: 'EARNINGS_DRIFT', label: 'EARN_DRFT' },
  { value: 'EXTENDED', label: 'EXTENDED' },
  { value: 'BROKEN', label: 'BROKEN' },
]

const orderBaseSchema = z
  .object({
    ticker: z.string().min(1, 'Ticker required'),
    setupType: z.string().min(1, 'Setup type required'),
    entryPrice: z.number({ error: 'Required' }).positive('Must be > 0'),
    stopPrice: z.number({ error: 'Required' }).positive('Must be > 0'),
    shares: z.number({ error: 'Required' }).int().positive('Must be > 0'),
    target2r: z.number().positive().optional(),
    target3r: z.number().positive().optional(),
    expirationDate: z.string().optional(),
    notes: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    if (data.entryPrice > 0 && data.stopPrice > 0 && data.entryPrice <= data.stopPrice) {
      ctx.addIssue({ code: 'custom', path: ['entryPrice'], message: 'Entry must be > stop' })
    }
    if (data.target2r != null && data.entryPrice > 0 && data.target2r <= data.entryPrice) {
      ctx.addIssue({ code: 'custom', path: ['target2r'], message: 'Must be > entry price' })
    }
    if (data.target3r != null && data.entryPrice > 0 && data.target3r <= data.entryPrice) {
      ctx.addIssue({ code: 'custom', path: ['target3r'], message: 'Must be > entry price' })
    }
    if (data.expirationDate) {
      const today = new Date().toISOString().slice(0, 10)
      if (data.expirationDate < today) {
        ctx.addIssue({ code: 'custom', path: ['expirationDate'], message: 'Must be today or later' })
      }
    }
  })

export const newOrderSchema = orderBaseSchema
export const editOrderSchema = orderBaseSchema

export type NewOrderFormValues = z.infer<typeof newOrderSchema>
export type EditOrderFormValues = z.infer<typeof editOrderSchema>
