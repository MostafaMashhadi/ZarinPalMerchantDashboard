import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ChevronDown, ChevronUp, Database, AlertTriangle } from 'lucide-react'
import type { InsightDTO, InsightKind, ProvenanceEntry } from '../services/types'
import { KIND_LABEL } from '../services/types'
import { cn } from '@/lib/utils'
import ProvenanceView from './ProvenanceView'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Tooltip,
} from 'recharts'

const KIND_ICON_HEX: Record<InsightKind, string> = {
  time_range: 'border-primary/20 bg-primary/10 text-primary',
  event_impact: 'border-gold/20 bg-gold/10 text-gold-deep',
  peer_comparison: 'border-leaf/20 bg-leaf/10 text-leaf',
  cohort_retention: 'border-royal-soft/20 bg-royal-soft/10 text-royal-soft',
  anomaly_detection: 'border-destructive/20 bg-destructive/10 text-destructive',
  agentic_summary: 'border-accent/30 bg-accent/10 text-accent',
}

const SEVERITY_CHIPS: Record<string, { label: string; className: string }> = {
  info: { label: 'اطلاع', className: 'badge-navy' },
  warning: { label: 'هشدار', className: 'badge-gold' },
  critical: { label: 'بحرانی', className: 'badge-red' },
}

interface InsightCardProps {
  insight: InsightDTO
  provenance?: ProvenanceEntry[]
  children?: React.ReactNode
  extraActions?: React.ReactNode
}

const InsightCard: React.FC<InsightCardProps> = ({ insight, provenance, children, extraActions }) => {
  const [showChart, setShowChart] = useState(false)

  const severityChip = insight.body.severity ? SEVERITY_CHIPS[insight.body.severity] : null

  return (
    <Card className={cn('card-zarin relative overflow-hidden animate-fade-in')}>
      <div className={cn('absolute inset-x-0 top-0 h-0.5 bg-gradient-to-l opacity-70', KIND_ICON_HEX[insight.kind])} />

      <CardHeader className="p-5 pb-1">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <Badge variant="outline" className={cn('text-[10px] font-bold', KIND_ICON_HEX[insight.kind])}>
            {KIND_LABEL[insight.kind]}
          </Badge>
          {severityChip && (
            <Badge variant="outline" className={cn('text-[10px] font-bold', severityChip.className)}>
              {severityChip.label}
            </Badge>
          )}
          <span className="text-[10px] font-bold text-muted-foreground">
            {new Date(insight.generated_at).toLocaleDateString('fa-IR')}
          </span>
        </div>

        <CardTitle className="text-base font-bold text-foreground leading-snug">{insight.headline}</CardTitle>
        {insight.low_confidence_peer_set && (
          <CardDescription className="flex items-start gap-2 text-xs text-gold-deep mt-1">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
            هم‌صنفی‌های کافی در دهک حجمی شما وجود نداشت؛ مقایسه با کل صنف انجام شده و ممکن است دقیق نباشد.
          </CardDescription>
        )}
      </CardHeader>

      <CardContent className="p-5 pt-2 space-y-4">
        <p className="text-sm leading-relaxed text-foreground/85">{insight.body.summary ?? insight.headline}</p>

        {children}

        <div className="flex flex-wrap items-center gap-2 pt-2">
          {extraActions}
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setShowChart((s) => !s)}
          >
            {showChart ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            {showChart ? 'مخفی کردن داده‌ها' : 'مشاهده داده‌ها'}
          </Button>
        </div>

        {showChart && (
          <div className="animate-fade-in rounded-xl border border-border/40 bg-muted/20 p-4">
            <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground mb-3">
              <Database className="size-3.5" />
              نمودار مربوط به این تحلیل
            </div>
            <div className="h-44 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={insight.body.series ?? []}>
                  <defs>
                    <linearGradient id={`chart-${insight.id}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#36B37E" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#36B37E" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <Area type="monotone" dataKey="value" stroke="#36B37E" strokeWidth={2} fill={`url(#chart-${insight.id})`} />
                  <Tooltip />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {provenance && <ProvenanceView rows={provenance} />}
      </CardContent>
    </Card>
  )
}

export default InsightCard
export { KIND_ICON_HEX, SEVERITY_CHIPS }
