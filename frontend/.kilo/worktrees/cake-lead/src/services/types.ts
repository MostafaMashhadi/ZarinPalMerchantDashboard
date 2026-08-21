export type InsightKind =
  | 'time_range'
  | 'event_impact'
  | 'peer_comparison'
  | 'cohort_retention'
  | 'anomaly_detection'
  | 'agentic_summary'

export type Freshness = 'live' | 'cached_fallback'

export interface HeadlineCard {
  key: string
  label: string
  value: number
  formatted: string
  delta: number
  unit: 'Rial' | '%' | 'count'
}

export interface DashboardSummary {
  period: { start: string; end: string }
  freshness: Freshness
  headline_cards: HeadlineCard[]
  merchant: {
    ref: string
    display_name: string
    category: string
  }
}

export interface InsightAction {
  text: string
  priority: 'low' | 'medium' | 'high' | 'critical'
}

export interface InsightBody {
  summary?: string
  sentences?: string[]
  actions?: InsightAction[]
  series?: Array<Record<string, unknown>>
  metrics?: Record<string, number | string>
  percentile?: number
  low_confidence_peer_set?: boolean
  severity?: 'info' | 'warning' | 'critical'
}

export interface InsightDTO {
  id: string
  merchant_ref: string
  kind: InsightKind
  headline: string
  body: InsightBody
  status: string
  low_confidence_peer_set: boolean
  period_start: string
  period_end: string
  generated_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface InsightFilters {
  kind?: InsightKind | ''
  period_start?: string
  period_end?: string
  page?: number
  page_size?: number
}

export interface ProvenanceEntry {
  sequence: number
  source_query_id: string
  clickhouse_sql: string
  query_params: Record<string, unknown>
  computed_at: string
  result_summary: Record<string, unknown>
}

export type RunStatus = 'running' | 'completed' | 'failed'

export interface AgentRunDTO {
  run_id: string
  poll_url: string
  status: RunStatus
  tokens_used: number
  cost: number
  checkpoint_step: string | null
  error?: string | null
}

export interface RunCostDTO {
  run_id: string
  status: RunStatus
  tokens_in: number
  tokens_out: number
  cost: number
  cost_usd: number
}

export type NotificationSeverity = 'info' | 'warning' | 'critical'

export interface NotificationDTO {
  id: string
  insight_id: string
  title: string
  body: string
  severity: NotificationSeverity
  channel: string
  status: 'pending' | 'sent' | 'failed'
  created_at: string
  read_at: string | null
}

export interface AuthTokens {
  access: string
  refresh: string
}

export interface AnalysisParams {
  time_range?: { period_start: string; period_end: string }
  event_impact?: { event_key: string }
  peer_comparison?: { period_start: string; period_end: string }
  cohort_retention?: { cohort_period_start: string; cohort_period_end: string; granularity: 'week' | 'month' }
  anomaly_detection?: { period_start: string; period_end: string }
}

export const KINDS: { id: InsightKind | ''; label: string }[] = [
  { id: '', label: 'همه بینش‌ها' },
  { id: 'time_range', label: 'بازه زمانی' },
  { id: 'event_impact', label: 'اثر رویداد' },
  { id: 'peer_comparison', label: 'مقایسه با هم‌صنفی‌ها' },
  { id: 'cohort_retention', label: 'نرخ بازگشت (کوهرت)' },
  { id: 'anomaly_detection', label: 'تشخیص ناهنجاری' },
  { id: 'agentic_summary', label: 'خلاصه هوشمند' },
]

export const KIND_LABEL: Record<InsightKind, string> = {
  time_range: 'بازه زمانی',
  event_impact: 'اثر رویداد',
  peer_comparison: 'مقایسه با هم‌صنفی‌ها',
  cohort_retention: 'نرخ بازگشت (کوهرت)',
  anomaly_detection: 'تشخیص ناهنجاری',
  agentic_summary: 'خلاصه هوشمند',
}

export type AgentRunErrorCode = 'ALL_PROVIDERS_EXHAUSTED' | 'COST_CEILING_EXCEEDED' | 'RUN_NOT_FOUND' | 'UNKNOWN'

export interface AgentRunError extends Error {
  code?: AgentRunErrorCode
}

export const AGENT_ERROR_MESSAGES: Record<AgentRunErrorCode, string> = {
  ALL_PROVIDERS_EXHAUSTED: 'امروز نتوانستم خلاصه هوشمند را تولید کنم، لطفاً بعداً دوباره تلاش کنید.',
  COST_CEILING_EXCEEDED: 'سقف هزینه روزانه رسیدیم، فردا دوباره تلاش کنید.',
  RUN_NOT_FOUND: 'این اجرا یافت نشد.',
  UNKNOWN: 'شکست در تولید خلاصه — دوباره تلاش کنید.',
}

export function mapAgentError(error: unknown): string {
  if (error instanceof Error) {
    const code = (error as AgentRunError).code
    if (code && AGENT_ERROR_MESSAGES[code]) {
      return AGENT_ERROR_MESSAGES[code]
    }
    if (error.message.includes('ALL_PROVIDERS_EXHAUSTED')) return AGENT_ERROR_MESSAGES.ALL_PROVIDERS_EXHAUSTED
    if (error.message.includes('COST_CEILING_EXCEEDED')) return AGENT_ERROR_MESSAGES.COST_CEILING_EXCEEDED
    if (error.message.includes('RUN_NOT_FOUND')) return AGENT_ERROR_MESSAGES.RUN_NOT_FOUND
  }
  return AGENT_ERROR_MESSAGES.UNKNOWN
}