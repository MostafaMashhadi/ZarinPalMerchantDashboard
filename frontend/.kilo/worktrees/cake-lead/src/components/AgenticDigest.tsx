import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Sparkles, RefreshCw, ChevronDown, Wind, CheckCircle2, AlertTriangle, Coins, Clock3 } from 'lucide-react'
import type { RootState, AppDispatch } from '../store/store'
import { triggerSummary, pollRunStatus, fetchRunCost, resetAgent } from '../store/agentSlice'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import api from '../services/api'
import type { InsightDTO } from '../services/types'
import { mapAgentError } from '../services/types'
import { cn } from '@/lib/utils'
import InsightCard from './InsightCard'

const CHECKPOINT_LABEL: Record<string, string> = {
  fetch_metrics:            'دریافت متریک‌ها از ClickHouse',
  segment_data:             'سگمنت‌بندی داده',
  detect_candidate_insights: 'شناسایی بینش‌های کاندید',
  rank_by_novelty:          'رتبه‌بندی بر اساس تازگی',
  draft_narrative:          'نگارش روایت (مدل زبانی)',
  validate_against_data:    'اعتبارسنجی اعداد با داده',
  publish_insight:          'انتشار بینش',
}

const POLL_INTERVAL = 2500

const AgenticDigest: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const merchantRef = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const { generating, run, cost, error } = useSelector((state: RootState) => state.agent)
  const [digest, setDigest] = useState<InsightDTO | null>(null)
  const [showChart, setShowChart] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const pollRef = useRef<number | null>(null)
  const elapsedRef = useRef<number | null>(null)

  const completedRun = run?.status === 'completed' ? run : null
  const friendlyError = error ? mapAgentError(error) : null
  const friendlyRunError = run?.status === 'failed' && run.error ? mapAgentError(run.error) : null

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    if (elapsedRef.current) {
      clearInterval(elapsedRef.current)
      elapsedRef.current = null
    }
    setElapsed(0)
  }, [])

  useEffect(() => {
    if (!completedRun) return
    if (cost === null && completedRun.status === 'completed') {
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

  useEffect(() => {
    if (!run || run.status !== 'running') return
    pollRef.current = window.setInterval(() => {
      dispatch(pollRunStatus({ merchantRef, runId: run.run_id }))
    }, POLL_INTERVAL)
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [run, merchantRef, dispatch])

  useEffect(() => {
    if (generating) {
      elapsedRef.current = window.setInterval(() => {
        setElapsed((e) => e + 1)
      }, 1000)
    }
    return () => {
      if (elapsedRef.current) {
        clearInterval(elapsedRef.current)
        elapsedRef.current = null
      }
    }
  }, [generating])

  const handleGenerate = () => {
    setDigest(null)
    setShowChart(false)
    stopPolling()
    dispatch(resetAgent())
    const end = new Date().toISOString()
    const start = new Date(Date.now() - 30 * 86400000).toISOString()
    const key = `summary-${merchantRef}-${start}-${Date.now()}`
    dispatch(triggerSummary({ merchantRef, period: { start, end }, idemKey: key }))
  }

  const formatElapsed = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="card-zarin relative overflow-hidden rounded-2xl bg-white">
      <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-l from-zarin-gold via-zarin-navy-soft to-zarin-green" />

      <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-4">
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

        {!generating && !run && (
          <Button onClick={handleGenerate} className="btn-zarin-primary shrink-0 gap-2 rounded-xl px-5 h-10 text-sm">
            <Sparkles className="size-4" />
            تولید خلاصه هفتگی
          </Button>
        )}
        {!generating && run?.status === 'failed' && (
          <Button onClick={handleGenerate} variant="outline" className="shrink-0 gap-2 rounded-xl border-destructive/30 text-destructive hover:bg-destructive/5 h-10 text-sm">
            <RefreshCw className="size-4" />
            تلاش مجدد
          </Button>
        )}
      </div>

      {generating && run?.status === 'running' && (
        <div className="flex items-center gap-4 border-t border-border/50 bg-primary/[0.03] px-6 py-5" role="status">
          <div className="relative shrink-0">
            <span className="block size-6 animate-spin rounded-full border-[3px] border-primary border-t-transparent" />
            <span className="absolute inset-0 size-6 animate-ping rounded-full border border-primary/25" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-bold text-foreground">در حال تولید خلاصه هوشمند هفتگی...</div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">
              {run.checkpoint_step ? CHECKPOINT_LABEL[run.checkpoint_step] ?? run.checkpoint_step : 'آماده‌سازی گردش کار'}
            </div>
          </div>
          <div className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
            <Clock3 className="size-3.5" />
            {formatElapsed(elapsed)}
          </div>
        </div>
      )}

      {!generating && run?.status === 'failed' && (
        <div className="flex items-center gap-3 border-t border-destructive/20 bg-destructive/5 px-6 py-4 text-sm text-destructive">
          <AlertTriangle className="size-4 shrink-0" />
          <span className="font-bold">{friendlyRunError ?? friendlyError ?? run.error ?? 'شکست در تولید خلاصه — دوباره تلاش کنید'}</span>
        </div>
      )}

      {!generating && run?.status === 'completed' && digest && (
        <div className="border-t border-border/50">
          <div className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
              <h3 className="text-lg font-black text-foreground leading-snug">{digest.headline}</h3>
              <div className="flex flex-wrap items-center gap-2">
                {cost && (
                  <span className="badge-green flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-bold tabular-nums">
                    <Coins className="size-3.5" />
                    هزینه: {cost.cost_usd.toFixed(4)} USD
                  </span>
                )}
                <Badge variant="outline" className="badge-navy rounded-full text-[10px] font-bold px-2.5 py-0.5">
                  {new Date(digest.generated_at).toLocaleDateString('fa-IR')}
                </Badge>
              </div>
            </div>
            <InsightCard insight={digest} />
          </div>
          <button
            type="button"
            onClick={() => setShowChart((s) => !s)}
            className="flex w-full items-center justify-between border-t border-border/50 bg-muted/20 px-6 py-3 text-xs font-bold text-muted-foreground transition-colors duration-200 hover:bg-muted/40 hover:text-foreground"
          >
            <span className="flex items-center gap-2">
              <Wind className="size-3.5" />
              مشاهده داده‌ها (See the data)
            </span>
            <ChevronDown className={cn('size-4 transition-transform duration-200', showChart && 'rotate-180')} />
          </button>
          {showChart && (
            <div className="animate-fade-in flex h-44 items-center justify-center border-t border-border/50 bg-card/60">
              <div className="text-center">
                <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-full border border-dashed border-border bg-muted/40">
                  <Wind className="size-5 opacity-40" />
                </div>
                <p className="text-xs text-muted-foreground">نمودار سری زمانی پس از اتصال به ClickHouse ترسیم می‌شود</p>
              </div>
            </div>
          )}
        </div>
      )}

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