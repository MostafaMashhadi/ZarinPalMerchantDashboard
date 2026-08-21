import React from 'react'
import type { InsightDTO } from '../services/types'
import InsightCard from './InsightCard'

const SEVERITY_MAP: Record<string, { label: string; color: string; bg: string }> = {
  info: { label: 'اطلاع', color: '#0D1B4B', bg: 'rgba(13,27,75,0.08)' },
  warning: { label: 'هشدار', color: '#C8841B', bg: 'rgba(245,166,35,0.12)' },
  critical: { label: 'بحرانی', color: '#C62828', bg: 'rgba(229,57,53,0.10)' },
}

interface AnomalyDetectionCardProps {
  insight: InsightDTO
  provenance?: { sequence: number; source_query_id: string; clickhouse_sql: string; query_params: Record<string, unknown>; computed_at: string; result_summary: Record<string, unknown> }[]
}

const AnomalyDetectionCard: React.FC<AnomalyDetectionCardProps> = ({ insight, provenance }) => {
  const body = insight.body as Record<string, unknown>
  const severity = (body.severity as string) ?? 'info'
  const score = (body.anomaly_score as number) ?? 0
  const meta = SEVERITY_MAP[severity] ?? SEVERITY_MAP.info

  return (
    <InsightCard insight={insight} provenance={provenance}>
      <div className="rounded-xl border border-border/40 bg-muted/20 p-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-xs font-bold text-muted-foreground mb-1">شدت ناهنجاری</div>
            <div className="text-lg font-black" style={{ color: meta.color }}>{meta.label}</div>
          </div>
          <div className="text-left">
            <div className="text-[10px] font-bold text-muted-foreground">امتیاز</div>
            <div className="text-lg font-black tabular-nums">{score.toFixed(2)}</div>
          </div>
        </div>
        <div className="mt-3 h-2 rounded-full bg-muted overflow-hidden">
          <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.min(100, score * 10)}%`, background: meta.color }} />
        </div>
      </div>
    </InsightCard>
  )
}

export default AnomalyDetectionCard
