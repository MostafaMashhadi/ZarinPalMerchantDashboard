import React, { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Lightbulb, ArrowLeft, FileCode2, Database, Layers, ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react'
import type { RootState, AppDispatch } from '../store/store'
import { fetchInsights, fetchInsightDetail, setKindFilter, setPage, clearDetail } from '../store/insightsSlice'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { KINDS } from '../services/types'
import type { InsightKind, InsightDTO, ProvenanceEntry } from '../services/types'
import InsightCard from './InsightCard'
import EventImpactCard from './EventImpactCard'
import CohortRetentionCard from './CohortRetentionCard'
import AnomalyDetectionCard from './AnomalyDetectionCard'
import PeerComparisonCard from './PeerComparisonCard'

const PAGE_WINDOW = 3

const CARD_COMPONENTS: Record<InsightKind, React.FC<{ insight: InsightDTO; provenance?: ProvenanceEntry[] }>> = {
  time_range: InsightCard,
  event_impact: EventImpactCard,
  peer_comparison: PeerComparisonCard,
  cohort_retention: CohortRetentionCard,
  anomaly_detection: AnomalyDetectionCard,
  agentic_summary: InsightCard,
}

interface InsightsPanelProps {
  preselectedId?: string | null
}

const InsightsPanel: React.FC<InsightsPanelProps> = ({ preselectedId }) => {
  const dispatch = useDispatch<AppDispatch>()
  const merchantRef = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const { filters, page: items, total, currentPage, pageSize, loading, error, detail, provenance, detailLoading, detailError } = useSelector(
    (state: RootState) => state.insights,
  )

  const [selectedId, setSelectedId] = useState<string | null>(preselectedId ?? null)

  useEffect(() => {
    setSelectedId(preselectedId ?? null)
  }, [preselectedId])

  useEffect(() => {
    dispatch(fetchInsights(merchantRef))
  }, [dispatch, merchantRef, currentPage, filters])

  useEffect(() => {
    if (preselectedId && merchantRef) {
      dispatch(clearDetail())
      dispatch(fetchInsightDetail({ merchantRef, insightId: preselectedId }))
    }
  }, [preselectedId, merchantRef, dispatch])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const openDetail = (id: string) => {
    setSelectedId(id)
    dispatch(clearDetail())
    dispatch(fetchInsightDetail({ merchantRef, insightId: id }))
  }

  const isoDate = (s: string) => {
    const d = new Date(s)
    return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString('fa-IR')
  }

  /* ------------------------------ DETAIL VIEW ------------------------------ */
  if (selectedId && detail) {
    const SpecificCard = CARD_COMPONENTS[detail.kind] ?? InsightCard
    return (
      <section className="space-y-5">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground hover:text-foreground" onClick={() => { setSelectedId(null); dispatch(clearDetail()) }}>
            <ArrowLeft className="size-4" />
            بازگشت به فهرست
          </Button>
        </div>

        {detailLoading && (
          <div className="flex h-48 items-center justify-center gap-3 text-sm text-muted-foreground">
            <div className="relative">
              <span className="size-5 animate-spin rounded-full border-[3px] border-primary border-t-transparent" />
              <div className="absolute inset-0 size-5 animate-ping rounded-full border border-primary/30" />
            </div>
            در حال بارگذاری جزئیات ...
          </div>
        )}

        {detailError && (
          <div className="flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-xs font-bold text-destructive animate-fade-in">
            <AlertTriangle className="size-3.5" />
            {detailError}
          </div>
        )}

        <SpecificCard insight={detail} provenance={provenance ?? []} />

        {/* Provenance — plain-language + SQL, in sequence order */}
        {provenance && provenance.length > 0 && (
          <div className="rounded-2xl border border-border/40 bg-white/70 p-6 backdrop-blur-sm">
            <div className="mb-1 flex items-center gap-2.5 text-base font-bold text-foreground">
               <Layers className="size-[18px] text-primary" />
              ردیابی منشأ (Provenance) — این بینش چگونه محاسبه شد؟
            </div>
            <p className="mb-5 text-sm leading-relaxed text-muted-foreground">
              هر عدد بر اساس کوئری‌های قابل تکرار روی تپل‌های روزانه ClickHouse ساخته شده است.
            </p>
            <ol className="space-y-4">
              {provenance.map((entry) => (
                <li key={entry.sequence} className="rounded-xl border border-border/40 bg-muted/20 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5 text-sm font-bold">
                      <span className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-[11px] font-black text-primary">
                        {entry.sequence + 1}
                      </span>
                      {entry.source_query_id}
                    </div>
                    <Badge variant="outline" className="text-[10px] font-bold text-muted-foreground">
                      محاسبه: {isoDate(entry.computed_at)}
                    </Badge>
                  </div>

                  <details className="mt-3">
                    <summary className="flex cursor-pointer items-center gap-2 text-xs font-bold text-muted-foreground transition-colors hover:text-foreground">
                      <FileCode2 className="size-3.5" />
                      مشاهده SQL
                    </summary>
                    <pre dir="ltr" className="mt-2 overflow-x-auto rounded-lg bg-foreground/[0.04] p-3 font-mono text-[11px] leading-relaxed text-foreground/80">
                      {entry.clickhouse_sql}
                    </pre>
                  </details>

                  {Object.keys(entry.result_summary).length > 0 && (
                    <div className="mt-3 flex items-center gap-2 text-[11px] text-muted-foreground">
                      <Database className="size-3.5" />
                      {Object.entries(entry.result_summary)
                        .map(([k, v]) => `${k}: ${String(v)}`)
                        .join(' · ')}
                    </div>
                  )}
                </li>
              ))}
            </ol>
          </div>
        )}
      </section>
    )
  }

  /* ------------------------------ LIST VIEW ------------------------------ */
  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2.5 text-base font-bold tracking-tight text-foreground">
            <Lightbulb className="size-[18px] text-primary" />
            بینش‌ها و تحلیل‌های شما
          </h2>
          <p className="mt-1 text-sm text-muted-foreground font-numeric">{total.toLocaleString('fa-IR')} بینش ثبت‌شده</p>
        </div>

        <div className="custom-scrollbar flex max-w-full gap-1.5 overflow-x-auto rounded-xl bg-muted/30 p-1">
          {KINDS.map((kind) => (
            <button
              key={kind.id}
              type="button"
              onClick={() => dispatch(setKindFilter(kind.id))}
              className={cn(
                'shrink-0 rounded-lg px-3 py-1.5 text-xs font-bold whitespace-nowrap transition-all duration-200',
                filters.kind === kind.id
                  ? 'bg-primary text-primary-foreground shadow-sm shadow-primary/20'
                  : 'text-muted-foreground hover:bg-white/80 hover:text-foreground',
              )}
            >
              {kind.label}
            </button>
          ))}
        </div>
      </div>

      {loading && items.length === 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-40 animate-pulse rounded-2xl border border-border/40 bg-white/60 p-5">
              <div className="mb-4 h-3 w-28 rounded-full bg-muted" />
              <div className="mb-3 h-4 w-3/4 rounded-full bg-muted" />
              <div className="h-3 w-1/2 rounded-full bg-muted" />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-xs font-bold text-destructive animate-fade-in">
          <AlertTriangle className="size-3.5" />
          {error}
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border/80 bg-white/50 px-4 py-12 text-center backdrop-blur-sm">
          <Lightbulb className="size-8 opacity-30" />
          <p className="text-base font-bold text-foreground">بینشی ثبت نشده است</p>
          <p className="max-w-sm text-sm text-muted-foreground">از تب «موتور تحلیلی» یک تحلیل اجرا کنید یا خلاصه هوشمند تولید کنید.</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {items.map((insight, index) => {
          const SpecificCard = CARD_COMPONENTS[insight.kind] ?? InsightCard
          const cardProvenance = provenance ?? []
          return (
            <div
              key={insight.id}
              onClick={() => openDetail(insight.id)}
              className="animate-fade-in cursor-pointer transition-all duration-300 ease-out hover:-translate-y-0.5"
              style={{ animationDelay: `${index * 60}ms` }}
            >
              <SpecificCard insight={insight} provenance={cardProvenance} />
            </div>
          )
        })}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between gap-4 border-t border-border/40 pt-5">
          <div className="text-xs text-muted-foreground font-numeric">
            صفحه {currentPage.toLocaleString('fa-IR')} از {totalPages.toLocaleString('fa-IR')} · {total.toLocaleString('fa-IR')} بینش
          </div>
          <div className="flex items-center gap-1.5">
            <Button variant="outline" size="sm" className="gap-1.5" disabled={currentPage <= 1} onClick={() => dispatch(setPage(currentPage - 1))}>
              <ChevronRight className="size-4" />
              قبلی
            </Button>
            {Array.from({ length: totalPages })
              .map((_, i) => i + 1)
              .filter((p) => p === 1 || p === totalPages || Math.abs(p - currentPage) < PAGE_WINDOW)
              .reduce<number[]>((acc, p, i, arr) => {
                if (i > 0 && p - arr[i - 1] > 1) acc.push(NaN)
                acc.push(p)
                return acc
              }, [])
              .map((p, i) =>
                Number.isNaN(p) ? (
                  <span key={`gap-${i}`} className="px-1 text-xs text-muted-foreground">
                    ...
                  </span>
                ) : (
                  <Button
                    key={p}
                    size="sm"
                    variant={p === currentPage ? 'default' : 'ghost'}
                    className={cn(
                      p === currentPage ? 'shadow-sm shadow-primary/20' : 'text-muted-foreground hover:text-foreground',
                      'font-numeric',
                    )}
                    onClick={() => dispatch(setPage(p))}
                  >
                    {p.toLocaleString('fa-IR')}
                  </Button>
                ),
              )}
            <Button variant="outline" size="sm" className="gap-1.5" disabled={currentPage >= totalPages} onClick={() => dispatch(setPage(currentPage + 1))}>
              بعدی
              <ChevronLeft className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </section>
  )
}

export default InsightsPanel
