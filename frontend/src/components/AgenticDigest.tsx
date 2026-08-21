import React, { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Sparkles, RefreshCw, ChevronDown, Wind, CheckCircle2, AlertTriangle, Clock3 } from 'lucide-react'
import type { RootState, AppDispatch } from '../store/store'
import { startSummary, fetchRunCost } from '../store/agentSlice'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import api from '../services/api'
import type { InsightDTO } from '../services/types'
import { cn } from '@/lib/utils'
import CostBreakdown from './CostBreakdown'
import InsightCard from './InsightCard'

/* ── Priority badge styling – ZarinPal palette ─────────────────── */
const PRIORITY_CHIP: Record<string, string> = {
  critical: 'border-red-200   bg-red-50   text-red-700',
  high:     'border-red-200   bg-red-50   text-red-700',
  medium:   'border-amber-200 bg-amber-50 text-amber-700',
  low:      'border-green-200 bg-green-50 text-green-700',
}

const CHECKPOINT_LABEL: Record<string, string> = {
  fetch_metrics:            'دریافت متریک‌ها از ClickHouse',
  segment_data:             'سگمنت‌بندی داده',
  detect_candidate_insights: 'شناسایی بینش‌های کاندید',
  rank_by_novelty:          'رتبه‌بندی بر اساس تازگی',
  draft_narrative:          'نگارش روایت (مدل زبانی)',
  validate_against_data:    'اعتبارسنجی اعداد با داده',
  publish_insight:          'انتشار بینش',
}

const merchantFacingFailure = (error?: string | null) => {
  if (error?.includes('AllProvidersExhausted')) return 'در حال حاضر امکان تولید خلاصه وجود ندارد؛ لطفاً کمی بعد دوباره تلاش کنید.'
  if (error?.includes('cost-ceiling') || error?.includes('COST_CEILING')) return 'تولید خلاصه به سقف هزینه مجاز رسید؛ تنظیمات خود را بررسی کنید.'
  return 'تولید خلاصه کامل نشد؛ لطفاً دوباره تلاش کنید.'
}

const AgenticDigest: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const merchantRef = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const { generating, run, cost } = useSelector((state: RootState) => state.agent)
  const [digest, setDigest] = useState<InsightDTO | null>(null)
  const [showChart, setShowChart] = useState(false)

  const completedRun = run?.status === 'completed' ? run : null

  useEffect(() => {
    if (!completedRun) return
    if (cost === null) {
      dispatch(fetchRunCost({ merchantRef, runId: completedRun.run_id }))
    }
  }, [completedRun, merchantRef, cost, dispatch])

  useEffect(() => {
    if (run?.status !== 'completed') return
    api
      .listInsights(merchantRef, { kind: 'agentic_summary', page_size: 1 })
      .then((page) => setDigest(page.items[0] ?? null))
      .catch(() => setDigest(null))
  }, [run?.status, run?.run_id, merchantRef])

  const handleGenerate = () => {
    setDigest(null)
    const end = new Date().toISOString()
    const start = new Date(Date.now() - 30 * 86400000).toISOString()
    dispatch(startSummary({ merchantRef, period: { start, end } }))
  }

  return (
    <div className="card-zarin relative overflow-hidden rounded-2xl bg-white">
      {/* Green-navy-gold tri-color accent stripe */}
      <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-l from-zarin-gold via-zarin-navy-soft to-zarin-green" />

      {/* ── Header row ── */}
      <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-4">
          {/* AI icon – gold with green pulse dot */}
          <div className="relative flex size-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-zarin-gold-dark to-zarin-gold shadow-lg shadow-amber-300/30 ring-1 ring-white/20 ring-inset">
            <Sparkles className="size-5 text-white" strokeWidth={2} />
            <span className="absolute -top-1 -end-1 size-3 rounded-full border-2 border-white bg-zarin-green shadow-sm animate-pulse-glow" />
          </div>

          <div>
            <h2 className="flex flex-wrap items-center gap-2 text-base font-black tracking-tight text-foreground">
              ایجنت هوشمند تحلیلی
              <span className="badge-navy rounded-full px-2.5 py-0.5 text-[10px] font-black">AI</span>
            </h2>
            <p className="mt-1 max-w-prose text-sm leading-relaxed text-muted-foreground">
              خلاصه هفتگی عملکرد پذیرنده — ۳ تا ۵ جمله + فهرست اقدام، با ردیابی کامل منشأ هر عدد
            </p>
          </div>
        </div>

        {/* CTA buttons */}
        {!generating && !run && (
          <Button
            onClick={handleGenerate}
            className="btn-zarin-primary shrink-0 gap-2 rounded-xl px-5 h-10 text-sm"
          >
            <Sparkles className="size-4" />
            تولید خلاصه هفتگی
          </Button>
        )}
        {!generating && run?.status === 'failed' && (
          <Button
            onClick={handleGenerate}
            variant="outline"
            className="shrink-0 gap-2 rounded-xl border-destructive/30 text-destructive hover:bg-destructive/5 h-10 text-sm"
          >
            <RefreshCw className="size-4" />
            تلاش مجدد
          </Button>
        )}
      </div>

      {/* ── Running state ── */}
      {generating && (
        <div
          className="flex items-center gap-4 border-t border-border/50 bg-primary/[0.03] px-6 py-5"
          role="status"
        >
          <div className="relative shrink-0">
            <span className="block size-6 animate-spin rounded-full border-[3px] border-primary border-t-transparent" />
            <span className="absolute inset-0 size-6 animate-ping rounded-full border border-primary/25" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-bold text-foreground">در حال تولید خلاصه هوشمند هفتگی...</div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">
              {run
                ? `گام: ${CHECKPOINT_LABEL[run.checkpoint_step ?? ''] ?? run.checkpoint_step}`
                : 'آماده‌سازی گردش کار'}
            </div>
          </div>
          <div className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
            <Clock3 className="size-3.5" />
            هر ۲-۳ ثانیه به‌روزرسانی
          </div>
        </div>
      )}

      {/* ── Failure state ── */}
      {!generating && run?.status === 'failed' && (
        <div className="flex items-center gap-3 border-t border-destructive/20 bg-destructive/5 px-6 py-4 text-sm text-destructive">
          <AlertTriangle className="size-4 shrink-0" />
          <span className="font-bold">{merchantFacingFailure(run.error)}</span>
        </div>
      )}

      {/* ── Completed digest ── */}
      {!generating && run?.status === 'completed' && digest && (
        <div className="border-t border-border/50 p-6">
          <InsightCard insight={digest}>
            {/* Headline + meta */}
            <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
              <h3 className="text-lg font-black text-foreground leading-snug">{digest.headline}</h3>
              <div className="flex flex-wrap items-center gap-2">
                {cost && <CostBreakdown cost={cost} scope="agent" />}
                <Badge
                  variant="outline"
                  className="badge-navy rounded-full text-[10px] font-bold px-2.5 py-0.5"
                >
                  {new Date(digest.generated_at).toLocaleDateString('fa-IR')}
                </Badge>
              </div>
            </div>

            {/* Summary bullets */}
            <ul className="space-y-3 mb-5">
              {(digest.body.sentences ?? []).map((sentence, i) => (
                <li key={i} className="flex items-start gap-3 text-sm leading-relaxed text-foreground/85">
                  <span
                    className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary"
                    aria-hidden="true"
                  />
                  {sentence}
                </li>
              ))}
            </ul>

            {/* Action items */}
            <div className="rounded-2xl border border-border/50 bg-muted/30 p-4">
              <div className="mb-3 text-xs font-bold text-muted-foreground">اقدامات پیشنهادی</div>
              <div className="flex flex-wrap gap-2">
                {(digest.body.actions ?? []).map((action, i) => (
                  <Badge
                    key={i}
                    variant="outline"
                    className={cn('text-[11px] font-bold rounded-lg', PRIORITY_CHIP[action.priority] ?? PRIORITY_CHIP.medium)}
                  >
                    {action.text}
                  </Badge>
                ))}
              </div>
            </div>
          {/* "See the data" expandable row */}
          <button
            type="button"
            onClick={() => setShowChart((s) => !s)}
            className="flex w-full items-center justify-between border-t border-border/50 bg-muted/20 px-6 py-3 text-xs font-bold text-muted-foreground transition-colors duration-200 hover:bg-muted/40 hover:text-foreground"
          >
            <span className="flex items-center gap-2">
              <Wind className="size-3.5" />
              مشاهده داده‌ها (See the data)
            </span>
            <ChevronDown
              className={cn('size-4 transition-transform duration-200', showChart && 'rotate-180')}
            />
          </button>

          {showChart && (
            <div className="animate-fade-in flex h-44 items-center justify-center border-t border-border/50 bg-card/60">
              <div className="text-center">
                <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-full border border-dashed border-border bg-muted/40">
                  <Wind className="size-5 opacity-40" />
                </div>
                <p className="text-xs text-muted-foreground">
                  نمودار سری زمانی پس از اتصال به ClickHouse ترسیم می‌شود
                </p>
              </div>
            </div>
          )}
          </InsightCard>
        </div>
      )}

      {/* ── Idle state ── */}
      {!generating && !run && (
        <div className="flex flex-col items-center gap-3 border-t border-border/50 bg-muted/20 px-6 py-10 text-center">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <CheckCircle2 className="size-5" />
          </div>
          <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
            یک خلاصه هوشمند تولید کنید تا ایجنت متریک‌ها را بازیابی کند، روایت بنویسد و اعداد را با داده خام اعتبارسنجی کند.
          </p>
        </div>
      )}
    </div>
  )
}

export default AgenticDigest
