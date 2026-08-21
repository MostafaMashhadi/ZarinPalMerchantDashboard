import React, { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { FlaskConical, CalendarDays, Scale, History, Radar, AlertTriangle, CheckCircle2 } from 'lucide-react'
import type { RootState, AppDispatch } from '../store/store'
import { runAnalysis, setKindFilter } from '../store/insightsSlice'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { InsightKind } from '../services/types'

const MOCK_EVENTS = [
  { key: 'nowruz', title: 'کمپین نوروز ۱۴۰۴' },
  { key: 'year_end', title: 'پیک خرید اسفند' },
  { key: 'summer_sale', title: 'حراج تابستانه' },
  { key: 'black_friday', title: 'جمعه سیاه' },
]

const ANALYSES: {
  kind: InsightKind
  title: string
  blurb: string
  icon: React.ReactNode
  accent: string
  needsPeriod: boolean
}[] = [
  {
    kind: 'time_range',
    title: 'تحلیل بازه زمانی',
    blurb: 'روند درآمد و متریک‌ها نسبت به دوره قبل (Time-Range)',
    icon: <History className="size-[18px]" />,
     accent: 'from-primary to-royal-soft',
     needsPeriod: true,
   },
   {
     kind: 'event_impact',
     title: 'اثر رویداد (Diff-in-Diff)',
     blurb: 'اثر یک کمپین یا رویداد بر درآمد شما نسبت به هم‌صنفی‌ها',
     icon: <CalendarDays className="size-[18px]" />,
     accent: 'from-gold-deep to-gold',
     needsPeriod: false,
   },
   {
     kind: 'peer_comparison',
     title: 'مقایسه با هم‌صنفی‌ها',
     blurb: 'موقعیت رقابتی شما در دهک حجمی هم‌صنفی‌ها (Peer Radar)',
     icon: <Scale className="size-[18px]" />,
     accent: 'from-leaf to-leaf-soft',
     needsPeriod: true,
   },
   {
     kind: 'cohort_retention',
     title: 'نرخ بازگشت (کوهرت)',
     blurb: 'منحنی بازگشت مشتریان با گرانولاریتی هفتگی/ماهانه',
     icon: <Radar className="size-[18px]" />,
     accent: 'from-royal-soft to-primary',
     needsPeriod: true,
   },
   {
     kind: 'anomaly_detection',
     title: 'تشخیص ناهنجاری',
     blurb: 'پرداخت‌های مکرر رها‌شده و الگوهای غیرعادی (Card-testing)',
     icon: <AlertTriangle className="size-[18px]" />,
     accent: 'from-destructive to-destructive/70',
     needsPeriod: true,
   },
]

interface FormValues {
  start: string
  end: string
  eventKey: string
  granularity: 'week' | 'month'
}

const todayISO = () => new Date().toISOString().slice(0, 10)
const daysAgo = (n: number) => new Date(Date.now() - n * 86400000).toISOString().slice(0, 10)

const AnalysesSuite: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const merchantRef = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const { runningKind, runningError } = useSelector((state: RootState) => state.insights)

  const [form, setForm] = useState<FormValues>({ start: daysAgo(30), end: todayISO(), eventKey: 'nowruz', granularity: 'week' })
  const [done, setDone] = useState<InsightKind | null>(null)

  const set = <K extends keyof FormValues>(key: K, value: FormValues[K]) => setForm((f) => ({ ...f, [key]: value }))

  const submit = async (kind: InsightKind) => {
    setDone(null)
    const period = { period_start: `${form.start}T00:00:00Z`, period_end: `${form.end}T23:59:59Z` }
    const cohort = { cohort_period_start: period.period_start, cohort_period_end: period.period_end, granularity: form.granularity }
    const params =
      kind === 'event_impact'
        ? { event_impact: { event_key: form.eventKey } }
        : kind === 'cohort_retention'
          ? { cohort_retention: cohort }
          : { time_range: period, peer_comparison: period, anomaly_detection: period }
    const result = await dispatch(runAnalysis({ merchantRef, kind, params }))
    if (runAnalysis.fulfilled.match(result)) {
      setDone(kind)
      dispatch(setKindFilter(kind))
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2.5 text-base font-bold tracking-tight text-foreground">
            <FlaskConical className="size-[18px] text-primary" />
            موتور تحلیلی — تحلیل‌های کلاسیک
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            هر تحلیل یک بینش با ردیابی منشأ کامل (Provenance) تولید و در فهرست بینش‌ها ذخیره می‌کند.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <label className="flex items-center gap-1.5">
            از تاریخ
            <Input type="date" value={form.start} onChange={(e) => set('start', e.target.value)} className="input-premium h-8 w-36" />
          </label>
          <label className="flex items-center gap-1.5">
            تا تاریخ
            <Input type="date" value={form.end} onChange={(e) => set('end', e.target.value)} className="input-premium h-8 w-36" />
          </label>
        </div>
      </div>

      {runningError && (
        <div className="flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-xs font-bold text-destructive animate-fade-in">
          <AlertTriangle className="size-3.5" />
          {runningError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {ANALYSES.map((analysis) => {
          const isRunning = runningKind === analysis.kind
          const isDone = done === analysis.kind
          return (
            <Card
              key={analysis.kind}
              className={cn(
                'group relative overflow-hidden border-border/40 bg-white/70 backdrop-blur-sm transition-all duration-300 ease-out hover:-translate-y-0.5 hover:border-black/8 hover:shadow-xl',
                isRunning && 'border-primary/30 shadow-lg shadow-primary/10',
              )}
            >
              {/* Top accent bar */}
              <div className={cn('absolute inset-x-0 top-0 h-0.5 bg-gradient-to-l opacity-70', analysis.accent)} />

              {/* Hover background effect */}
              <div className="absolute inset-0 bg-gradient-to-br from-primary/3 via-transparent to-leaf/3 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

              <CardHeader className="relative flex-row items-start justify-between gap-2 p-5 pb-1">
                <div className="flex items-center gap-3">
                  <div className={cn('flex size-9 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-sm', analysis.accent)}>
                    {analysis.icon}
                  </div>
                  <div>
                    <CardTitle className="text-sm font-bold text-foreground">{analysis.title}</CardTitle>
                    <CardDescription className="mt-0.5 text-[11px] leading-relaxed">{analysis.blurb}</CardDescription>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="relative space-y-3 p-5 pt-2.5">
                {analysis.kind === 'event_impact' ? (
                  <select
                    value={form.eventKey}
                    onChange={(e) => set('eventKey', e.target.value)}
                    className="input-premium h-8 w-full rounded-lg border border-input bg-card px-2.5 text-sm font-medium outline-none"
                  >
                    {MOCK_EVENTS.map((ev) => (
                      <option key={ev.key} value={ev.key}>
                        {ev.title}
                      </option>
                    ))}
                  </select>
                ) : analysis.kind === 'cohort_retention' ? (
                  <div className="flex gap-2">
                    <select
                      value={form.granularity}
                      onChange={(e) => set('granularity', e.target.value as FormValues['granularity'])}
                      className="input-premium h-8 w-full rounded-lg border border-input bg-card px-2.5 text-sm font-medium outline-none"
                    >
                      <option value="week">هفتگی</option>
                      <option value="month">ماهانه</option>
                    </select>
                  <div className="flex-1 rounded-lg bg-muted/50 px-3 py-1 text-[11px] font-bold text-muted-foreground font-numeric">
                    {new Date(`${form.start}`).toLocaleDateString('fa-IR')} تا {new Date(`${form.end}`).toLocaleDateString('fa-IR')}
                  </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2 text-[11px] font-bold text-muted-foreground font-numeric">
                    <span>بازه پیش‌فرض ۳۰ روز</span>
                    <span>
                      {new Date(`${form.start}`).toLocaleDateString('fa-IR')} ← {new Date(`${form.end}`).toLocaleDateString('fa-IR')}
                    </span>
                  </div>
                )}

                <Button
                  variant={analysis.kind === 'anomaly_detection' ? 'default' : 'outline'}
                  size="sm"
                  className="btn-premium w-full gap-2"
                  disabled={isRunning}
                  onClick={() => submit(analysis.kind)}
                >
                  {isRunning ? (
                    <>
                      <span className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      در حال محاسبه...
                    </>
                  ) : (
                    <>
                      <FlaskConical className="size-3.5" />
                      اجرای تحلیل
                    </>
                  )}
                </Button>

                {isDone && (
                  <div className="flex items-center gap-2 text-[11px] font-bold text-leaf animate-fade-in">
                    <CheckCircle2 className="size-3.5" />
                    بینش ساخته شد — به فهرست بینش‌ها اضافه شد
                  </div>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </section>
  )
}

export default AnalysesSuite
