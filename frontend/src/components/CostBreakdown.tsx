import { Coins } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { RunCostDTO } from '@/services/types'

interface CostBreakdownProps {
  cost: RunCostDTO
  scope: 'agent' | 'chat'
}

/** Compact, scope-aware cost summary shared by agent runs and future chat turns. */
export default function CostBreakdown({ cost, scope }: CostBreakdownProps) {
  const label = scope === 'agent' ? 'هزینه اجرای ایجنت' : 'هزینه گفتگو'
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <Badge variant="outline" className="gap-1.5"><Coins aria-hidden="true" />{label}: {cost.cost_usd.toFixed(4)} USD</Badge>
      <span className="font-numeric">ورودی: {cost.tokens_in.toLocaleString('fa-IR')}</span>
      <span className="font-numeric">خروجی: {cost.tokens_out.toLocaleString('fa-IR')}</span>
    </div>
  )
}
