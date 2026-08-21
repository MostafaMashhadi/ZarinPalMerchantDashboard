import React from 'react'
import { AlertTriangle } from 'lucide-react'
import type { InsightDTO } from '../services/types'
import InsightCard from './InsightCard'

interface PeerComparisonCardProps {
  insight: InsightDTO
  provenance?: { sequence: number; source_query_id: string; clickhouse_sql: string; query_params: Record<string, unknown>; computed_at: string; result_summary: Record<string, unknown> }[]
}

const PeerComparisonCard: React.FC<PeerComparisonCardProps> = ({ insight, provenance }) => {
  const body = insight.body as Record<string, unknown>
  const percentile = (body.percentile as number) ?? 50
  const isLowConfidence = insight.low_confidence_peer_set

  return (
    <InsightCard insight={insight} provenance={provenance}>
      <div className="rounded-xl border border-border/40 bg-muted/20 p-4">
        <div className="text-xs font-bold text-muted-foreground mb-2">موقعیت شما در دهک حجمی هم‌صنفی‌ها</div>
        <div className="flex items-end gap-3">
          <div className="text-3xl font-black tabular-nums">{percentile.toLocaleString('fa-IR')}٪</div>
          <div className="text-xs text-muted-foreground mb-1">بیشتر از هم‌صنفی‌های خود</div>
        </div>
        <div className="mt-3 h-2 rounded-full bg-muted overflow-hidden">
          <div className="h-full rounded-full bg-primary transition-all duration-700" style={{ width: `${Math.min(100, percentile)}%` }} />
        </div>
      </div>
      {isLowConfidence && (
        <div className="flex items-start gap-2 rounded-xl border border-gold/30 bg-gold/5 px-3 py-2.5 text-xs font-bold text-gold-deep">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          هم‌صنفی‌های کافی در دهک حجمی شما وجود نداشت؛ مقایسه با کل صنف انجام شده و ممکن است دقیق نباشد.
        </div>
      )}
    </InsightCard>
  )
}

export default PeerComparisonCard
