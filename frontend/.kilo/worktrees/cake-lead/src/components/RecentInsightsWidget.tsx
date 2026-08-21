import React, { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Lightbulb, ChevronLeft } from 'lucide-react'
import type { RootState, AppDispatch } from '../store/store'
import { fetchInsights } from '../store/insightsSlice'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Link } from 'react-router-dom'
import { KIND_LABEL } from '../services/types'
import type { InsightKind } from '../services/types'
import { cn } from '@/lib/utils'

const RecentInsightsWidget: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const merchantRef = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const page = useSelector((state: RootState) => state.insights.page)
  const insightsLoading = useSelector((state: RootState) => state.insights.loading)
  const [localLoading, setLocalLoading] = useState(true)
  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true
    dispatch(fetchInsights(merchantRef))
      .finally(() => setLocalLoading(false))
  }, [dispatch, merchantRef])

  const recent = page.slice(0, 5)

  return (
    <div className="card-zarin rounded-2xl bg-white">
      <div className="p-5 pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Lightbulb className="size-4" />
            </div>
            <div>
              <h3 className="text-sm font-black text-foreground">بینش‌های اخیر</h3>
              <p className="text-[11px] font-bold text-muted-foreground">آخرین تحلیل‌های خود را بررسی کنید</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" className="gap-1.5 text-xs text-muted-foreground hover:text-foreground" asChild>
            <Link to="/insights">
              مشاهده همه
              <ChevronLeft className="size-3.5" />
            </Link>
          </Button>
        </div>
      </div>

      <div className="px-5 pb-5">
        {(localLoading || insightsLoading) ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 rounded-xl border border-border/40 bg-muted/20 p-3">
                <Skeleton className="size-8 shrink-0 rounded-lg" />
                <div className="flex-1 min-w-0">
                  <Skeleton className="mb-1.5 h-3.5 w-3/4 rounded-full" />
                  <Skeleton className="h-2.5 w-1/2 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        ) : recent.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <div className="flex size-10 items-center justify-center rounded-full bg-muted/50">
              <Lightbulb className="size-4 opacity-50" />
            </div>
            <p className="text-xs font-bold text-muted-foreground">هنوز بینشی ثبت نشده است</p>
            <p className="text-[11px] text-muted-foreground/70">از تب «موتور تحلیلی» یک تحلیل اجرا کنید</p>
          </div>
        ) : (
          <div className="space-y-2">
            {recent.map((insight, index) => {
              const kind = insight.kind as InsightKind
              return (
                <Link
                  key={insight.id}
                  to={`/insights/${insight.id}`}
                  className={cn(
                    'flex items-center gap-3 rounded-xl border border-border/40 bg-muted/20 p-3',
                    'transition-all duration-200 hover:border-border hover:bg-muted/40 hover:shadow-sm',
                    'animate-fade-in',
                  )}
                  style={{ animationDelay: `${index * 60}ms` }}
                >
                  <span className={cn('flex size-8 shrink-0 items-center justify-center rounded-lg text-[10px] font-black', {
                    'bg-primary/10 text-primary': kind === 'time_range',
                    'bg-gold/10 text-gold-deep': kind === 'event_impact',
                    'bg-leaf/10 text-leaf': kind === 'peer_comparison',
                    'bg-royal-soft/10 text-royal-soft': kind === 'cohort_retention',
                    'bg-destructive/10 text-destructive': kind === 'anomaly_detection',
                    'bg-accent/10 text-accent': kind === 'agentic_summary',
                  })}>
                    {KIND_LABEL[kind].charAt(0)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-foreground">{insight.headline}</p>
                    <p className="truncate text-[11px] text-muted-foreground">
                      {KIND_LABEL[kind]} · {new Date(insight.generated_at).toLocaleDateString('fa-IR')}
                    </p>
                  </div>
                  <Badge variant="outline" className={cn('hidden sm:flex text-[10px] font-bold shrink-0', {
                    'badge-green': insight.body.severity === 'info' || !insight.body.severity,
                    'badge-gold': insight.body.severity === 'warning',
                    'badge-red': insight.body.severity === 'critical',
                  })}>
                    {insight.body.severity ? (insight.body.severity === 'info' ? 'اطلاع' : insight.body.severity === 'warning' ? 'هشدار' : 'بحرانی') : KIND_LABEL[kind]}
                  </Badge>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default RecentInsightsWidget