import React, { useState, useEffect, useCallback } from 'react'
import { useSelector } from 'react-redux'
import type { RootState } from '../store/store'
import { api } from '../services/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertTriangle, RefreshCw, Coins } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CostEntry {
  run_id: string
  status: string
  tokens_in: number
  tokens_out: number
  cost: number
  cost_usd: number
  merchant_ref: string
  created_at: string
}

const OpsCostPage: React.FC = () => {
  const merchantRef = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const [runs, setRuns] = useState<CostEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [realtime, setRealtime] = useState({ tokens_in: 0, tokens_out: 0, cost: 0, cost_usd: 0 })

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    ;(async () => {
      try {
        const insights = await api.listInsights(merchantRef, { kind: 'agentic_summary', page: 1, page_size: 50 })
        const costs: CostEntry[] = []
        for (const item of insights.items) {
          try {
            const cost = await api.getRunCost(merchantRef, item.id)
            costs.push({ ...cost, merchant_ref: merchantRef, created_at: item.generated_at })
          } catch {
            // skip
          }
        }
        setRuns(costs.sort((a, b) => b.created_at.localeCompare(a.created_at)))
        const total = costs.reduce((acc, c) => ({ tokens_in: acc.tokens_in + c.tokens_in, tokens_out: acc.tokens_out + c.tokens_out, cost: acc.cost + c.cost, cost_usd: acc.cost_usd + c.cost_usd }), { tokens_in: 0, tokens_out: 0, cost: 0, cost_usd: 0 })
        setRealtime(total)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'خطا در دریافت هزینه‌ها')
      } finally {
        setLoading(false)
      }
    })()
  }, [merchantRef])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2.5 text-base font-bold tracking-tight text-foreground">
            <Coins className="size-[18px] text-primary" />
            داشبورد هزینه‌ها (Ops)
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">هزینه لحظه‌ای و تاریخی مصرف ایجنت هوشمند</p>
        </div>
        <Button variant="outline" size="sm" className="gap-2" onClick={load} disabled={loading}>
          <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
          به‌روزرسانی
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-xs font-bold text-destructive">
          <AlertTriangle className="size-3.5" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 lg:gap-5">
        <Card className="card-zarin">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground">توکن‌های ورودی</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-black tabular-nums">{realtime.tokens_in.toLocaleString('fa-IR')}</div>
          </CardContent>
        </Card>
        <Card className="card-zarin">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground">توکن‌های خروجی</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-black tabular-nums">{realtime.tokens_out.toLocaleString('fa-IR')}</div>
          </CardContent>
        </Card>
        <Card className="card-zarin">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground">هزینه کل (USD)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-black tabular-nums">{realtime.cost_usd.toFixed(4)}</div>
          </CardContent>
        </Card>
        <Card className="card-zarin">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground">تعداد اجراها</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-black tabular-nums">{runs.length.toLocaleString('fa-IR')}</div>
          </CardContent>
        </Card>
      </div>

      <Card className="card-zarin overflow-hidden">
        <CardHeader>
          <CardTitle className="text-sm font-bold">تاریخچه هزینه‌ها</CardTitle>
          <CardDescription>جزئیات هر اجرای ایجنت هوشمند</CardDescription>
        </CardHeader>
        <CardContent>
          {runs.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">هنوز اجرایی ثبت نشده است</div>
          ) : (
            <div className="space-y-3">
              {runs.map((run) => (
                <div key={run.run_id} className="flex items-center justify-between gap-4 rounded-xl border border-border/40 bg-muted/20 p-4">
                  <div>
                    <div className="text-sm font-bold">{run.run_id}</div>
                     <div className="text-xs text-muted-foreground font-numeric">{new Date(run.created_at).toLocaleString('fa-IR')}</div>
                  </div>
                  <div className="flex items-center gap-4 text-xs">
                    <span className="tabular-nums">IN: {run.tokens_in.toLocaleString('fa-IR')}</span>
                    <span className="tabular-nums">OUT: {run.tokens_out.toLocaleString('fa-IR')}</span>
                    <span className="font-black tabular-nums">{run.cost_usd.toFixed(4)} USD</span>
                    <Badge variant="outline" className={cn(
                      'text-[10px] font-bold',
                      run.status === 'completed' ? 'badge-green' : run.status === 'failed' ? 'badge-red' : 'badge-gold'
                    )}>
                      {run.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default OpsCostPage
