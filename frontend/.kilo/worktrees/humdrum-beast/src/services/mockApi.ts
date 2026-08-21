import { mockMerchants } from './mockData'
import type {
  AgentRunDTO,
  AnalysisParams,
  AuthTokens,
  DashboardSummary,
  InsightDTO,
  InsightFilters,
  InsightKind,
  NotificationDTO,
  Page,
  ProvenanceEntry,
  RunCostDTO,
} from './types'

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const num = (value: number, unit: 'Rial' | '%' | 'count' = 'count'): string => {
  const s = value.toLocaleString('fa-IR')
  if (unit === 'Rial') return `${s} تومان`
  if (unit === '%') return `${s}٪`
  return s
}

let simulateLockout = false
export let _lockoutRetryAfterSeconds = 60

const iso = (daysAgo: number) => new Date(Date.now() - daysAgo * 86400000).toISOString()

let insightSeq = 100
const makeInsight = (kind: InsightKind, merchantRef: string, headline: string): InsightDTO => {
  insightSeq += 1
  const generatedAt = iso(0)
  const sent = [
    `درآمد کل این دوره ${num(pidValue(kind), 'Rial')} بود که نسبت به دوره قبل ${deltaFor()}٪ تغییر کرد.`,
    `نرخ موفقیت تراکنش‌ها ${Math.round(88 + Math.random() * 6).toLocaleString('fa-IR')}٪ برآورد می‌شود.`,
    `بیشترین رشد در ${['اسفند', 'اواسط هفته', 'پایان ماه'][Math.floor(Math.random() * 3)]} مشاهده شد.`,
  ]
  return {
    id: `ins-${insightSeq}`,
    merchant_ref: merchantRef,
    kind,
    headline,
    body: {
      summary: sent.join(' '),
      sentences: sent,
      actions: [
        { text: 'این مسیر را در گزارش هفتگی لحاظ کنید', priority: 'medium' },
        { text: 'مقایسه با هم‌صنفی‌ها انجام شود', priority: 'low' },
      ],
      severity: kind === 'anomaly_detection' ? 'critical' : kind === 'event_impact' ? 'warning' : 'info',
    },
    status: 'published',
    low_confidence_peer_set: kind === 'peer_comparison' && Math.random() > 0.7,
    period_start: iso(30),
    period_end: iso(0),
    generated_at: generatedAt,
  }
}

const pidValue = (kind: InsightKind) =>
  ({ time_range: 4.2e8, event_impact: 6.1e7, peer_comparison: 5.5e8, cohort_retention: 3.2e8, anomaly_detection: 1.1e8, agentic_summary: 4.8e8 })[kind]
const deltaFor = () => Math.round((Math.random() * 32 - 4) * 10) / 10

const pool = new Map<string, InsightDTO[]>()
const getPool = (merchantRef: string): InsightDTO[] => {
  if (!pool.has(merchantRef)) {
    pool.set(merchantRef, [
      makeInsight('time_range', merchantRef, 'روند رشد درآمد در ۳۰ روز گذشته'),
      makeInsight('event_impact', merchantRef, 'اثر کمپین نوروز بر تراکنش‌ها'),
      makeInsight('peer_comparison', merchantRef, `شما در ${Math.floor(84 + Math.random() * 15).toLocaleString('fa-IR')}٪ برتر هم‌صنفی‌های خود هستید`),
      makeInsight('cohort_retention', merchantRef, 'نرخ بازگشت مشتریان هفته اول تا چهارم'),
      makeInsight('anomaly_detection', merchantRef, 'الگوی غیرعادی در پرداخت‌های رها‌شده تشخیص داده شد'),
      makeInsight('agentic_summary', merchantRef, 'خلاصه هوشمند هفتگی عملکرد پذیرنده'),
    ])
  }
  return pool.get(merchantRef)!
}

const merchantOf = (ref: string) => mockMerchants.find((m) => m.id === ref) ?? mockMerchants[0]

const runs = new Map<string, { run: AgentRunDTO; startedAt: number }>()

export type MockApi = {
  login(email: string, password: string): Promise<AuthTokens>
  getDashboardSummary(merchantRef: string): Promise<DashboardSummary>
  listInsights(merchantRef: string, filters: InsightFilters): Promise<Page<InsightDTO>>
  getInsight(merchantRef: string, insightId: string): Promise<InsightDTO>
  getInsightProvenance(merchantRef: string, insightId: string): Promise<ProvenanceEntry[]>
  runAnalysis(merchantRef: string, kind: InsightKind, params: AnalysisParams): Promise<InsightDTO>
  triggerSummary(merchantRef: string, period: { start: string; end: string }, idemKey: string): Promise<AgentRunDTO>
  getRunStatus(merchantRef: string, runId: string): Promise<AgentRunDTO>
  getRunCost(merchantRef: string, runId: string): Promise<RunCostDTO>
  listNotifications(merchantRef: string, status?: string): Promise<NotificationDTO[]>
  markNotificationRead(merchantRef: string, id: string): Promise<NotificationDTO>
  simulateLockout(retryAfter?: number): void
}

export const mockApi: MockApi = {
  async login() {
    await delay(400)
    if (simulateLockout) {
      simulateLockout = false
      throw new Error('LOCKED')
    }
    return { access: 'mock-access-token', refresh: 'mock-refresh-token' }
  },

  async getDashboardSummary(merchantRef) {
    await delay(350)
    const m = merchantOf(merchantRef)
    return {
      period: { start: iso(30), end: iso(0) },
      freshness: 'live',
      merchant: { ref: m.id, display_name: m.name, category: m.category },
      headline_cards: [
        { key: 'gross_volume', label: 'مجموع فروش محقق‌شده', value: 426_000_000, formatted: num(426_000_000, 'Rial'), delta: 12.4, unit: 'Rial' },
        { key: 'success_rate', label: 'نرخ موفقیت', value: 94.7, formatted: num(94.7, '%'), delta: 5.2, unit: '%' },
        { key: 'failed_volume', label: 'تراکنش‌های ناموفق', value: 8.2, formatted: num(8.2, '%'), delta: -4.3, unit: '%' },
        { key: 'avg_basket', label: 'میانگین سبد خرید', value: 63, formatted: num(6300000, 'Rial'), delta: 2.8, unit: 'Rial' },
      ],
    }
  },

  async listInsights(merchantRef, filters) {
    await delay(300)
    const all = getPool(merchantRef).filter((i) => !filters.kind || i.kind === filters.kind)
    const pageSize = filters.page_size ?? 6
    const page = filters.page ?? 1
    const items = all.slice((page - 1) * pageSize, page * pageSize)
    return { items, total: all.length, page, page_size: pageSize }
  },

  async getInsight(_merchantRef, insightId) {
    await delay(200)
    for (const list of pool.values()) {
      const found = list.find((i) => i.id === insightId)
      if (found) return found
    }
    throw new Error('NOT_FOUND')
  },

  async getInsightProvenance(_merchantRef, insightId) {
    await delay(250)
    const rows = [
      { period: 'event window', metric: 'gross_volume', source: 'tx_daily_rollup', sql: `SELECT sumMerge(gross_volume) AS gross_volume FROM tx_daily_rollup WHERE merchant_key = %(merchant_key)s AND day BETWEEN %(start)s AND %(end)s GROUP BY merchant_key` },
      { period: 'control window', metric: 'gross_volume', source: 'tx_daily_rollup', sql: `SELECT sumMerge(gross_volume) AS gross_volume FROM tx_daily_rollup WHERE merchant_key = %(merchant_key)s AND day BETWEEN %(start)s AND %(end)s AND period_flag = 'control' GROUP BY merchant_key` },
    ]
    return rows.slice(0, insightId.endsWith('1') ? 1 : 2).map((r, idx) => ({
      sequence: idx,
      source_query_id: `${insightId}:${r.period}:${r.metric}`,
      clickhouse_sql: r.sql,
      query_params: { merchant_key: 'M18', start: iso(30), end: iso(0) },
      computed_at: iso(0),
      result_summary: { gross_volume: 426_000_000, rows: 1 },
    }))
  },

  async runAnalysis(merchantRef, kind, _params) {
    await delay(600)
    const headlines: Record<InsightKind, string> = {
      time_range: 'تحلیل بازه زمانی — روند و مقایسه با دوره قبل',
      event_impact: 'اثر رویداد انتخابی بر درآمد شما نسبت به هم‌صنفی‌ها',
      peer_comparison: 'موقعیت رقابتی شما در دهک حجمی هم‌صنفی‌ها',
      cohort_retention: 'منحنی بازگشت مشتریان بر اساس گرانولاریتی انتخابی',
      anomaly_detection: 'ناهنجاری در الگوی پرداخت — نیازمند بررسی',
      agentic_summary: 'خلاصه هوشمند دوره',
    }
    const insight = makeInsight(kind, merchantRef, headlines[kind])
    const list = getPool(merchantRef)
    list.unshift(insight)
    return insight
  },

  async triggerSummary(merchantRef, _period, idemKey) {
    await delay(500)
    const runId = `run-${Math.round(Math.random() * 1e6)}`
    const run: AgentRunDTO = { run_id: runId, poll_url: `/api/v1/merchants/${merchantRef}/agent/runs/${runId}`, status: 'running', tokens_used: 0, cost: 0, checkpoint_step: 'fetch_metrics' }
    runs.set(idemKey, { run, startedAt: Date.now() })
    return run
  },

  async getRunStatus(_merchantRef, runId) {
    await delay(400)
    for (const { run, startedAt } of runs.values()) {
      if (run.run_id !== runId) continue
      const elapsed = Date.now() - startedAt
      if (elapsed > 6000) {
        run.status = 'completed'
        run.tokens_used = 4200
        run.cost = 0.084
        run.checkpoint_step = 'publish_insight'
        return { ...run }
      }
      run.checkpoint_step = elapsed > 3000 ? 'draft_narrative' : 'fetch_metrics'
      return { ...run }
    }
    return { run_id: runId, poll_url: '', status: 'failed', tokens_used: 0, cost: 0, checkpoint_step: null, error: 'RUN_NOT_FOUND' }
  },

  async getRunCost(_merchantRef, runId) {
    await delay(200)
    for (const { run } of runs.values()) {
      if (run.run_id !== runId) continue
      return { run_id: runId, status: run.status, tokens_in: 2800, tokens_out: 1400, cost: run.cost, cost_usd: run.cost }
    }
    return { run_id: runId, status: 'failed', tokens_in: 0, tokens_out: 0, cost: 0, cost_usd: 0 }
  },

  async listNotifications(_merchantRef, status) {
    await delay(200)
    const base: NotificationDTO[] = [
      { id: 'n-1', insight_id: 'ins-105', title: 'ناهنجاری در پرداخت‌های رها‌شده', body: 'الگوی تکراری در ترمینال اصلی مشاهده شد.', severity: 'critical', channel: 'portal', status: 'sent', created_at: iso(0), read_at: null },
      { id: 'n-2', insight_id: 'ins-102', title: 'اثر کمپین نوروز', body: 'اثر مثبت کمپین نوروز بر تراکنش‌ها تایید شد.', severity: 'warning', channel: 'portal', status: 'sent', created_at: iso(1), read_at: null },
      { id: 'n-3', insight_id: 'ins-103', title: 'موقعیت رقابتی', body: 'خلاصه هفتگی هم‌صنفی‌ها آماده است.', severity: 'info', channel: 'portal', status: 'sent', created_at: iso(2), read_at: iso(2) },
    ]
    return status ? base.filter((n) => n.status === status) : base
  },

  async markNotificationRead(_merchantRef, id) {
    await delay(150)
    // notifications are derived; mark-read is a no-op in mock (state resets on refetch)
    return { id, insight_id: '', title: '', body: '', severity: 'info', channel: 'portal', status: 'sent', created_at: iso(0), read_at: new Date().toISOString() } as NotificationDTO
  },

  simulateLockout(retryAfter = 60) {
    simulateLockout = true
    _lockoutRetryAfterSeconds = retryAfter
  },
}