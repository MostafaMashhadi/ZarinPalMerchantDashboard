import React, { useState, useEffect, useCallback } from 'react'
import { useSelector } from 'react-redux'
import type { RootState } from '../store/store'
import { api } from '../services/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertTriangle, RefreshCw, Coins, Bot, MessagesSquare } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CostDashboardDTO, CostScopeSummary } from '@/services/types'

const scopeMeta = {
  agent: { label: 'ایجنت', description: 'تحلیل‌ها و خلاصه‌های برنامه‌ریزی‌شده', icon: Bot },
  chat: { label: 'گفتگو', description: 'پرسش‌وپاسخ‌های تعاملی پذیرنده', icon: MessagesSquare },
} as const

function ScopeCard({ value }: { value: CostScopeSummary }) {
  const meta = scopeMeta[value.scope]
  const Icon = meta.icon
  return <Card className="card-zarin"><CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-sm"><Icon className="size-4 text-primary" /> {meta.label}</CardTitle><CardDescription>{meta.description}</CardDescription></CardHeader><CardContent className="space-y-2"><p className="text-2xl font-black tabular-nums" dir="ltr">${value.cost_usd.toFixed(4)}</p><div className="flex justify-between text-xs text-muted-foreground"><span>{value.runs.toLocaleString('fa-IR')} اجرا/پیام</span><span className="font-numeric">{(value.tokens_in + value.tokens_out).toLocaleString('fa-IR')} توکن</span></div></CardContent></Card>
}

const OpsCostPage: React.FC = () => {
  const merchantRef = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const [data, setData] = useState<CostDashboardDTO | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => { setLoading(true); setError(null); try { setData(await api.getCostDashboard(merchantRef)) } catch (e) { setError(e instanceof Error ? e.message : 'خطا در دریافت هزینه‌ها') } finally { setLoading(false) } }, [merchantRef])
  useEffect(() => { void load() }, [load])
  const agent = data?.realtime.find((item) => item.scope === 'agent')
  const chat = data?.realtime.find((item) => item.scope === 'chat')

  return <div className="space-y-6 animate-fade-in">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="flex items-center gap-2.5 text-base font-bold tracking-tight"><Coins className="size-[18px] text-primary" /> داشبورد هزینه‌ها (Ops)</h2><p className="mt-1 text-sm text-muted-foreground">هزینه لحظه‌ای Redis و سابقه ثبت‌شده؛ تفکیک‌شده بر اساس دامنه مصرف</p></div><Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}><RefreshCw className={cn('size-3.5', loading && 'animate-spin')} /> به‌روزرسانی</Button></div>
    {error && <div className="flex items-center gap-2 rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm text-muted-foreground" role="alert"><AlertTriangle className="size-4" />{error}<Button variant="ghost" size="sm" onClick={() => void load()}>تلاش دوباره</Button></div>}
    <section aria-label="هزینه لحظه‌ای"><h3 className="mb-3 text-sm font-bold">هزینه لحظه‌ای</h3><div className="grid gap-4 md:grid-cols-2">{agent && <ScopeCard value={agent} />}{chat && <ScopeCard value={chat} />}</div></section>
    <Card className="card-zarin overflow-hidden"><CardHeader><CardTitle className="text-sm font-bold">سابقه هزینه بر پایه دامنه</CardTitle><CardDescription>رکوردهای دفتر هزینه بر اساس تاریخ و پذیرنده؛ هزینه گفتگو با ایجنت ادغام نمی‌شود.</CardDescription></CardHeader><CardContent>{!data?.historical.length ? <div className="py-8 text-center text-sm text-muted-foreground">هنوز رکوردی ثبت نشده است</div> : <div className="space-y-2">{data.historical.map((entry, index) => { const meta = scopeMeta[entry.scope]; const Icon = meta.icon; return <div key={`${entry.scope}-${entry.date}-${index}`} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/50 bg-muted/20 p-3"><div className="flex items-center gap-3"><span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary"><Icon className="size-4" /></span><div><p className="text-sm font-bold">{meta.label}</p><p className="text-xs text-muted-foreground">{entry.merchant_ref} · {new Date(entry.date).toLocaleDateString('fa-IR')}</p></div></div><div className="flex items-center gap-3"><Badge variant="outline">{entry.runs.toLocaleString('fa-IR')} اجرا</Badge><span className="font-numeric text-sm font-bold" dir="ltr">${entry.cost_usd.toFixed(4)}</span></div></div> })}</div>}</CardContent></Card>
  </div>
}
export default OpsCostPage
