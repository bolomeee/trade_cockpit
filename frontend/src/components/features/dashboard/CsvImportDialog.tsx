import { useEffect, useRef, useState } from 'react'
import { FileText, Loader2, Upload } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { bulkAddStocks } from '@/lib/api/watchlist'
import { ApiError } from '@/lib/api/client'
import type { BulkAddResult } from '@/types/watchlist'

const BULK_MAX = 200

function parseTickers(raw: string): string[] {
  const seen = new Set<string>()
  return raw
    .split(/[\n,\r\t]+/)
    .map((t) => t.trim().replace(/^["']|["']$/g, '').toUpperCase())
    .filter((t) => {
      if (!t || t === 'TICKER' || t === 'SYMBOL') return false
      if (seen.has(t)) return false
      seen.add(t)
      return true
    })
    .slice(0, BULK_MAX)
}

type Phase = 'input' | 'importing' | 'done' | 'error'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

export function CsvImportDialog({ open, onOpenChange, onSuccess }: Props) {
  const [phase, setPhase] = useState<Phase>('input')
  const [activeTab, setActiveTab] = useState('file')
  const [textValue, setTextValue] = useState('')
  const [tickers, setTickers] = useState<string[]>([])
  const [result, setResult] = useState<BulkAddResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) {
      setPhase('input')
      setActiveTab('file')
      setTextValue('')
      setTickers([])
      setResult(null)
      setErrorMsg(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }, [open])

  useEffect(() => {
    if (activeTab === 'text') {
      setTickers(parseTickers(textValue))
    }
  }, [textValue, activeTab])

  const handleTabChange = (val: string) => {
    setActiveTab(val)
    setTickers([])
    setTextValue('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const text = await file.text()
    setTickers(parseTickers(text))
  }

  const handleImport = async () => {
    if (tickers.length === 0) return
    setPhase('importing')
    try {
      const res = await bulkAddStocks(tickers)
      setResult(res)
      setPhase('done')
      onSuccess()
    } catch (err) {
      const code = err instanceof ApiError ? err.code : 'UNKNOWN'
      setErrorMsg(
        code === 'EXTERNAL_API_ERROR'
          ? '导入失败（FMP 服务异常），请重试'
          : '导入失败，请重试',
      )
      setPhase('error')
    }
  }

  const isImporting = phase === 'importing'
  const canImport = tickers.length > 0 && phase === 'input'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>批量导入 Watchlist</DialogTitle>
        </DialogHeader>

        {(phase === 'input' || phase === 'importing') && (
          <>
            <Tabs value={activeTab} onValueChange={handleTabChange}>
              <TabsList className="w-full">
                <TabsTrigger value="file" className="flex-1">
                  文件上传
                </TabsTrigger>
                <TabsTrigger value="text" className="flex-1">
                  文本粘贴
                </TabsTrigger>
              </TabsList>

              <TabsContent value="file" className="mt-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.txt"
                  className="hidden"
                  onChange={handleFileChange}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex w-full flex-col items-center gap-2 rounded-lg border-2 border-dashed border-border py-6 text-sm text-muted-foreground transition-colors hover:border-ring hover:text-foreground"
                >
                  <FileText size={24} strokeWidth={1.5} />
                  <span>点击选择 CSV / TXT 文件</span>
                  <span className="text-xs">每行一个 ticker，或逗号分隔</span>
                </button>
              </TabsContent>

              <TabsContent value="text" className="mt-3">
                <Textarea
                  placeholder={'AAPL\nMSFT\nGOOGL\n或用逗号分隔: AAPL,MSFT,GOOGL'}
                  className="h-28 resize-none font-mono text-xs"
                  value={textValue}
                  onChange={(e) => setTextValue(e.target.value)}
                />
              </TabsContent>
            </Tabs>

            <TickerPreview tickers={tickers} />
          </>
        )}

        {phase === 'done' && result && (
          <ImportResult result={result} />
        )}

        {phase === 'error' && (
          <p className="text-sm text-destructive">{errorMsg}</p>
        )}

        <DialogFooter>
          {phase === 'done' && (
            <Button onClick={() => onOpenChange(false)}>完成</Button>
          )}
          {phase === 'error' && (
            <>
              <Button variant="outline" onClick={() => setPhase('input')}>
                返回
              </Button>
              <Button onClick={handleImport}>重试</Button>
            </>
          )}
          {(phase === 'input' || isImporting) && (
            <Button onClick={handleImport} disabled={!canImport || isImporting}>
              {isImporting ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  导入中…
                </>
              ) : (
                <>
                  <Upload size={14} />
                  导入 {tickers.length > 0 ? `(${tickers.length})` : ''}
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TickerPreview({ tickers }: { tickers: string[] }) {
  if (tickers.length === 0) return null
  const SHOW_MAX = 8
  const shown = tickers.slice(0, SHOW_MAX)
  const rest = tickers.length - SHOW_MAX

  return (
    <div className="rounded-md bg-muted/50 px-3 py-2 text-xs">
      <p className="mb-1 font-medium text-foreground">
        已解析 {tickers.length} 个 ticker
        {tickers.length === BULK_MAX && (
          <span className="ml-1 text-muted-foreground">(已截断至上限 {BULK_MAX})</span>
        )}
      </p>
      <p className="font-mono text-muted-foreground">
        {shown.join(', ')}
        {rest > 0 && <span> … 还有 {rest} 个</span>}
      </p>
    </div>
  )
}

function ImportResult({ result }: { result: BulkAddResult }) {
  const { added, skippedDuplicate, notFound } = result
  return (
    <div className="space-y-2 text-sm">
      <ResultRow icon="✅" label="已添加" items={added.map((s) => s.ticker)} />
      <ResultRow icon="⏭" label="跳过（重复）" items={skippedDuplicate} />
      <ResultRow icon="❌" label="未找到" items={notFound} />
    </div>
  )
}

function ResultRow({ icon, label, items }: { icon: string; label: string; items: string[] }) {
  return (
    <div className="flex items-start gap-2">
      <span>{icon}</span>
      <span className="text-muted-foreground">{label}：</span>
      <span className="font-medium">
        {items.length === 0 ? (
          <span className="text-muted-foreground">无</span>
        ) : (
          `${items.length} 个（${items.slice(0, 5).join(', ')}${items.length > 5 ? ' …' : ''}）`
        )}
      </span>
    </div>
  )
}
