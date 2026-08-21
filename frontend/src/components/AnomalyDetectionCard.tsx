import React from 'react'
import type { InsightDTO } from '../services/types'
import InsightCard from './InsightCard'
import { severityFor, severityPresentation } from '@/lib/severity'
import { cn } from '@/lib/utils'

interface AnomalyDetectionCardProps {
  insight: InsightDTO
  provenance?: { sequence: number; source_query_id: string; clickhouse_sql: string; query_params: Record<string, unknown>; computed_at: string; result_summary: Record<string, unknown> }[]
}

const AnomalyDetectionCard: React.FC<AnomalyDetectionCardProps> = ({ insight, provenance }) => {
  const body = insight.body as Record<string, unknown>
  const severity = severityFor(body.severity)
  const meta = severityPresentation[severity]

  return (
    <InsightCard insight={insight} provenance={provenance}>
      <div className="rounded-xl border border-border/40 bg-muted/20 p-4">
        <p className="text-xs font-bold text-muted-foreground">شدت ناهنجاری</p>
        <p className={cn('mt-2 inline-flex rounded-full border px-3 py-1 text-sm font-bold', meta.className)}>{meta.label}</p>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">این مورد برای بررسی تیم پرداخت علامت‌گذاری شده است.</p>
      </div>
    </InsightCard>
  )
}

export default AnomalyDetectionCard
