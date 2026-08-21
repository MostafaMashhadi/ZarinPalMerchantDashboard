import React from 'react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { InsightDTO } from '../services/types'
import InsightCard from './InsightCard'

interface CohortRetentionCardProps {
  insight: InsightDTO
  provenance?: { sequence: number; source_query_id: string; clickhouse_sql: string; query_params: Record<string, unknown>; computed_at: string; result_summary: Record<string, unknown> }[]
  onGranularityChange?: (granularity: string) => void
}

const CohortRetentionCard: React.FC<CohortRetentionCardProps> = ({ insight, provenance, onGranularityChange }) => {
  const body = insight.body as Record<string, unknown>
  const granularity = (body.granularity as string) ?? 'week'

  return (
    <InsightCard insight={insight} provenance={provenance}>
      <div className="flex items-center gap-2">
        <Select value={granularity} onValueChange={onGranularityChange}>
          <SelectTrigger className="h-8 w-32 text-xs">
            <SelectValue placeholder="گرانولاریتی" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="week">هفتگی</SelectItem>
            <SelectItem value="month">ماهانه</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {Boolean(body.retention_curve) && Array.isArray(body.retention_curve) && (
        <div className="h-44 w-full">
          <CurveChart data={body.retention_curve as Array<{ label: string; value: number }>} />
        </div>
      )}
    </InsightCard>
  )
}

const CurveChart: React.FC<{ data: Array<{ label: string; value: number }> }> = ({ data }) => (
  <div className="flex items-end gap-1 h-full w-full px-2">
    {data.map((pt, i) => (
      <div key={i} className="flex flex-1 flex-col items-center gap-1">
        <div className="w-full rounded-t-md bg-primary/80 transition-all duration-500" style={{ height: `${Math.max(4, Number(pt.value))}%` }} />
        <span className="text-[9px] text-muted-foreground truncate w-full text-center">{String(pt.label)}</span>
      </div>
    ))}
  </div>
)

export default CohortRetentionCard
