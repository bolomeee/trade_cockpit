import { useEffect } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { getUserSettings, updateUserSettings, type UserSettings } from '../lib/api/userSettingsApi'

const schema = z.object({
  accountSize: z.number().positive('Account size must be > 0'),
  maxExposurePct: z.number().min(0, 'Min 0').max(100, 'Max 100'),
  singleTradeRiskPct: z.number().min(0, 'Min 0').max(5, 'Max 5'),
  defaultRiskPerTradePct: z.number().min(0, 'Min 0').max(5, 'Max 5'),
  baseCurrency: z.string(),
})

type FormValues = z.infer<typeof schema>

type Props = {
  open: boolean
  onClose: () => void
}

export function UserSettingsDialog({ open, onClose }: Props) {
  const queryClient = useQueryClient()

  const { data: settings } = useQuery({
    queryKey: ['cockpit-user-settings'],
    queryFn: getUserSettings,
    staleTime: Infinity,
  })

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      accountSize: 100000,
      maxExposurePct: 80,
      singleTradeRiskPct: 1.0,
      defaultRiskPerTradePct: 0.75,
      baseCurrency: 'USD',
    },
  })

  useEffect(() => {
    if (settings) {
      form.reset({
        accountSize: settings.accountSize,
        maxExposurePct: settings.maxExposurePct,
        singleTradeRiskPct: settings.singleTradeRiskPct,
        defaultRiskPerTradePct: settings.defaultRiskPerTradePct,
        baseCurrency: settings.baseCurrency,
      })
    }
  }, [settings]) // eslint-disable-line react-hooks/exhaustive-deps

  const mutation = useMutation({
    mutationFn: updateUserSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cockpit-user-settings'] })
      queryClient.invalidateQueries({ queryKey: ['cockpit-decision'] })
      onClose()
    },
  })

  const onSubmit = (data: FormValues) => {
    const dirty = form.formState.dirtyFields
    const patch: Partial<Omit<UserSettings, 'updatedAt'>> = {}
    if (dirty.accountSize) patch.accountSize = data.accountSize
    if (dirty.maxExposurePct) patch.maxExposurePct = data.maxExposurePct
    if (dirty.singleTradeRiskPct) patch.singleTradeRiskPct = data.singleTradeRiskPct
    if (dirty.defaultRiskPerTradePct) patch.defaultRiskPerTradePct = data.defaultRiskPerTradePct
    if (dirty.baseCurrency) patch.baseCurrency = data.baseCurrency

    if (Object.keys(patch).length === 0) {
      onClose()
      return
    }
    mutation.mutate(patch)
  }

  const fieldStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  }

  const errorStyle: React.CSSProperties = {
    fontSize: 'var(--font-size-caption)',
    color: 'var(--color-signal-danger)',
    marginTop: '2px',
  }

  const { errors } = form.formState

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent showCloseButton>
        <DialogHeader>
          <DialogTitle>User Settings</DialogTitle>
          <DialogDescription>实际 risk% = min(regime 推荐, 上方设置, 单次 override)</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '4px 0' }}>
            <div style={fieldStyle}>
              <Label htmlFor="accountSize">Account size</Label>
              <Input
                id="accountSize"
                type="number"
                step="any"
                {...form.register('accountSize', { valueAsNumber: true })}
              />
              {errors.accountSize && (
                <span style={errorStyle}>{errors.accountSize.message}</span>
              )}
            </div>

            <div style={fieldStyle}>
              <Label htmlFor="maxExposurePct">Max exposure %</Label>
              <Input
                id="maxExposurePct"
                type="number"
                step="any"
                {...form.register('maxExposurePct', { valueAsNumber: true })}
              />
              {errors.maxExposurePct && (
                <span style={errorStyle}>{errors.maxExposurePct.message}</span>
              )}
            </div>

            <div style={fieldStyle}>
              <Label htmlFor="singleTradeRiskPct">Single-trade risk %</Label>
              <Input
                id="singleTradeRiskPct"
                type="number"
                step="any"
                {...form.register('singleTradeRiskPct', { valueAsNumber: true })}
              />
              {errors.singleTradeRiskPct && (
                <span style={errorStyle}>{errors.singleTradeRiskPct.message}</span>
              )}
            </div>

            <div style={fieldStyle}>
              <Label htmlFor="defaultRiskPerTradePct">Default risk per trade %</Label>
              <Input
                id="defaultRiskPerTradePct"
                type="number"
                step="any"
                {...form.register('defaultRiskPerTradePct', { valueAsNumber: true })}
              />
              {errors.defaultRiskPerTradePct && (
                <span style={errorStyle}>{errors.defaultRiskPerTradePct.message}</span>
              )}
            </div>

            <div style={fieldStyle}>
              <Label htmlFor="baseCurrency">Base currency</Label>
              <Controller
                control={form.control}
                name="baseCurrency"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="baseCurrency">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="USD">USD</SelectItem>
                      {/* v1.9: add CNY, HKD */}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>

            {mutation.isError && (
              <p style={{ ...errorStyle, marginTop: 0 }}>
                保存失败，请重试
              </p>
            )}
          </div>

          <DialogFooter style={{ marginTop: '8px' }}>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Saving…' : 'Save Settings'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
