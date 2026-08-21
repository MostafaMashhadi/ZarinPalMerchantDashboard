import { useState } from 'react'
import { Braces, Database, FileCode2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { ProvenanceEntry } from '@/services/types'

interface ProvenanceViewProps {
  rows: ProvenanceEntry[]
  title?: string
}

/** Reusable, collapsed query lineage for insights today and chat messages in Sprint 3. */
export default function ProvenanceView({ rows, title = 'مشاهده کوئری' }: ProvenanceViewProps) {
  const [expanded, setExpanded] = useState(false)
  const orderedRows = [...rows].sort((a, b) => a.sequence - b.sequence)

  if (orderedRows.length === 0) return null

  return (
    <section className="flex flex-col gap-3" aria-label="ردیابی منشأ داده">
      <Button variant="ghost" size="sm" className="w-fit text-muted-foreground" onClick={() => setExpanded((value) => !value)}>
        <FileCode2 data-icon="inline-start" aria-hidden="true" />
        {expanded ? 'بستن کوئری‌ها' : title}
      </Button>
      {expanded && (
        <div className="flex flex-col gap-3">
          {orderedRows.map((row) => (
            <Card key={`${row.source_query_id}-${row.sequence}`} size="sm" className="bg-muted/30">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <span className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-xs text-primary">{row.sequence + 1}</span>
                  {row.source_query_id}
                </CardTitle>
                <CardDescription>{row.ingest_batch_id ? `بچ ورودی: ${row.ingest_batch_id}` : 'بچ ورودی ثبت نشده است'}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="flex flex-col gap-1">
                  <span className="flex items-center gap-1 text-xs text-muted-foreground"><FileCode2 aria-hidden="true" /> ClickHouse SQL</span>
                  <pre dir="ltr" className="overflow-x-auto rounded-lg bg-background p-3 text-xs leading-6 text-foreground">{row.clickhouse_sql}</pre>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="flex items-center gap-1 text-xs text-muted-foreground"><Braces aria-hidden="true" /> پارامترهای کوئری</span>
                  <pre dir="ltr" className="overflow-x-auto rounded-lg bg-background p-3 text-xs leading-6 text-foreground">{JSON.stringify(row.query_params, null, 2)}</pre>
                </div>
                <p className="flex items-center gap-1 text-xs text-muted-foreground"><Database aria-hidden="true" /> محاسبه‌شده در {new Date(row.computed_at).toLocaleString('fa-IR')}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  )
}
