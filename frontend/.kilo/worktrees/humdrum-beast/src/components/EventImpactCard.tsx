import React from 'react'
import { AlertTriangle } from 'lucide-react'
import type { InsightDTO } from '../services/types'
import InsightCard from './InsightCard'

interface EventImpactCardProps {
  insight: InsightDTO
  provenance?: { sequence: number; source_query_id: string; clickhouse_sql: string; query_params: Record<string, unknown>; computed_at: string; result_summary: Record<string, unknown> }[]
}

const EventImpactCard: React.FC<EventImpactCardProps> = ({ insight, provenance }) => {
  const body = insight.body as Record<string, unknown>
  const controlWindowQuality = (body as Record<string, string>).control_window_quality as string | undefined

  return (
    <InsightCard insight={insight} provenance={provenance}>
      {controlWindowQuality === 'yearly_fallback' && (
        <div className="flex items-center gap-2 rounded-xl border border-gold/30 bg-gold/5 px-3 py-2 text-xs font-bold text-gold-deep">
          <AlertTriangle className="size-3.5 shrink-0" />
          مقایسه این بازه با داده‌های سال گذشته انجام شده است
        </div>
      )}
      {(body.diff_in_diff_delta != null || body.event_delta != null) && (
        <div className="rounded-xl border border-border/40 bg-muted/20 p-4">
          <div className="text-xs font-bold text-muted-foreground mb-1">تفاوت مشاهده شده</div>
          <div className="text-2xl font-black tabular-nums">
            {(body.diff_in_diff_delta ?? body.event_delta ?? 0) as number}٪
          </div>
        </div>
      )}
    </InsightCard>
  )
}

export default EventImpactCard
