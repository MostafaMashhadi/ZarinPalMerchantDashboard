import React, { useMemo, useState } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { InsightDTO, ProvenanceEntry } from '../services/types'
import InsightCard from './InsightCard'

type CurvePoint = { label: string; value: number }
type Cohort = { verify_type?: string; label?: string; retention_curve?: CurvePoint[] }

interface CohortRetentionCardProps {
  insight: InsightDTO
  provenance?: ProvenanceEntry[]
}

const CohortRetentionCard: React.FC<CohortRetentionCardProps> = ({ insight, provenance }) => {
  const body = insight.body as Record<string, unknown>
  const cohorts = useMemo(() => (Array.isArray(body.cohorts) ? body.cohorts as Cohort[] : []), [body.cohorts])
  const [selectedVerifyType, setSelectedVerifyType] = useState(cohorts[0]?.verify_type ?? '')
  const selected = cohorts.find((cohort) => cohort.verify_type === selectedVerifyType)
  const curve = selected?.retention_curve ?? (Array.isArray(body.retention_curve) ? body.retention_curve as CurvePoint[] : [])

  return (
    <InsightCard insight={insight} provenance={provenance}>
      {cohorts.length > 1 && (
        <Select value={selectedVerifyType} onValueChange={setSelectedVerifyType}>
          <SelectTrigger className="w-44"><SelectValue placeholder="سگمنت مشتریان" /></SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {cohorts.map((cohort) => <SelectItem key={cohort.verify_type} value={cohort.verify_type ?? ''}>{cohort.label ?? cohort.verify_type}</SelectItem>)}
            </SelectGroup>
          </SelectContent>
        </Select>
      )}
      {curve.length > 0 && <RetentionCurve data={curve} />}
    </InsightCard>
  )
}

function RetentionCurve({ data }: { data: CurvePoint[] }) {
  return (
    <div className="h-48 w-full" aria-label="منحنی نرخ بازگشت مشتریان">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} />
          <YAxis tickLine={false} axisLine={false} unit="%" tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} />
          <Tooltip formatter={(value) => [`${value}%`, 'نرخ بازگشت']} />
          <Line type="monotone" dataKey="value" stroke="var(--primary)" strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default CohortRetentionCard
