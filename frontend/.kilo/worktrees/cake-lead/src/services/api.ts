import { mockApi } from './mockApi'
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

/** Set VITE_API_BASE_URL to the DRF origin (e.g. http://localhost:8000).
 *  Set VITE_USE_MOCK=false to talk to the real backend once it is up. */
const API_BASE: string = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1') as string
export const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? 'true') === 'true'

export class ApiError extends Error {
  status: number
  code?: string
  retryAfterSeconds?: number
  constructor(status: number, code: string | undefined, message: string, retryAfterSeconds?: number) {
    super(message)
    this.status = status
    this.code = code
    this.retryAfterSeconds = retryAfterSeconds
  }
}

/** Access token is stored in memory only (lost on refresh → forces re-login).
 *  Refresh token is persisted in localStorage to enable the silent-refresh interceptor.
 *  This is a common security trade-off: short-lived access tokens can't be stolen
 *  from persistent storage, while the refresh token enables seamless re-auth. */
let accessToken: string | null = null
let refreshToken: string | null = localStorage.getItem('zp_refresh')

const TOKEN_KEYS = { access: 'zp_access', refresh: 'zp_refresh' }

export function setTokens(tokens: AuthTokens | null) {
  accessToken = tokens?.access ?? null
  refreshToken = tokens?.refresh ?? null
  if (tokens) {
    localStorage.setItem(TOKEN_KEYS.refresh, tokens.refresh)
  } else {
    localStorage.removeItem(TOKEN_KEYS.refresh)
  }
}

export async function hydrateTokensFromStorage() {
  refreshToken = localStorage.getItem(TOKEN_KEYS.refresh)
  if (refreshToken && !accessToken) {
    await refreshAccessToken()
  }
}

export const isAuthenticated = () => Boolean(accessToken || refreshToken)

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; idempotencyKey?: string; retry?: boolean } = {},
): Promise<T> {
  const { method = 'GET', body, idempotencyKey, retry = true } = options
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey

  const resp = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  // 401 → try a single refresh, then replay the original request once.
  if (resp.status === 401 && retry && refreshToken && !path.startsWith('/auth/')) {
    const refreshed = await refreshAccessToken()
    if (refreshed) return request<T>(path, { ...options, retry: false })
    // refresh failed → force logout
    setTokens(null)
    window.dispatchEvent(new CustomEvent('auth:logout'))
    throw new ApiError(401, 'AUTH_EXPIRED', 'نشست شما منقضی شده است')
  }

  if (resp.status === 429) {
    const data = (await resp.json().catch(() => ({}))) as { error?: string; retry_after_seconds?: number }
    throw new ApiError(429, data.error ?? 'RATE_LIMITED', 'محدودیت نرخ درخواست — کمی بعد دوباره تلاش کنید', data.retry_after_seconds ?? 1)
  }

  if (resp.status === 423) {
    const data = (await resp.json().catch(() => ({}))) as { error?: string; detail?: string; retry_after_seconds?: number }
    throw new ApiError(423, data.error ?? 'LOCKED', data.detail ?? 'حساب شما قفل شده است', data.retry_after_seconds ?? 60)
  }

  if (!resp.ok) {
    const data = (await resp.json().catch(() => ({}))) as { error?: string; detail?: string; message?: string }
    throw new ApiError(resp.status, data.error, data.detail ?? data.message ?? `خطای ${resp.status}`)
  }

  const data = (await resp.json()) as T & { data_freshness?: string }
  if (data.data_freshness === 'cached_fallback') {
    window.dispatchEvent(new CustomEvent('ui:data-degraded'))
  }

  return data as T
}

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshToken) return false
  try {
    const resp = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: refreshToken }),
    })
    if (!resp.ok) {
      setTokens(null)
      return false
    }
    const data = (await resp.json()) as { access: string }
    setTokens({ access: data.access, refresh: refreshToken })
    return true
  } catch {
    return false
  }
}

/** Path here is the sub-path under /auth (login|refresh|logout). */
export const authApi = {
  login: (email: string, password: string) =>
    USE_MOCK
      ? mockApi.login(email, password)
      : request<AuthTokens>('/auth/login', { method: 'POST', body: { email, password }, retry: false }),
  logout: () =>
    USE_MOCK ? Promise.resolve({ ok: true }) : request<{ ok: boolean }>('/auth/logout', { method: 'POST', retry: false }),
}

export const api = {
  getDashboardSummary: (merchantRef: string) =>
    USE_MOCK ? mockApi.getDashboardSummary(merchantRef) : request<DashboardSummary>(`/merchants/${merchantRef}/dashboard/summary`),

  listInsights: (merchantRef: string, filters: InsightFilters) => {
    const q = new URLSearchParams()
    if (filters.kind) q.set('kind', filters.kind)
    if (filters.period_start) q.set('period_start', filters.period_start)
    if (filters.period_end) q.set('period_end', filters.period_end)
    q.set('page', String(filters.page ?? 1))
    if (filters.page_size) q.set('page_size', String(filters.page_size))
    return USE_MOCK
      ? mockApi.listInsights(merchantRef, filters)
      : request<Page<InsightDTO>>(`/merchants/${merchantRef}/insights?${q.toString()}`)
  },

  getInsight: (merchantRef: string, insightId: string) =>
    USE_MOCK ? mockApi.getInsight(merchantRef, insightId) : request<InsightDTO>(`/merchants/${merchantRef}/insights/${insightId}`),

  getInsightProvenance: (merchantRef: string, insightId: string) =>
    USE_MOCK
      ? mockApi.getInsightProvenance(merchantRef, insightId)
      : request<ProvenanceEntry[]>(`/merchants/${merchantRef}/insights/${insightId}/provenance`),

  runAnalysis: (merchantRef: string, kind: InsightKind, params: AnalysisParams) =>
    USE_MOCK
      ? mockApi.runAnalysis(merchantRef, kind, params)
      : request<InsightDTO>(`/merchants/${merchantRef}/analysis/${kind}`, {
          method: 'POST',
          body: (params[kind as Exclude<InsightKind, 'agentic_summary'>] ?? {}),
        }),

  triggerSummary: (merchantRef: string, period: { start: string; end: string }, idemKey: string) => {
    const idem = idemKey || `summary-${merchantRef}-${period.start}`
    return USE_MOCK
      ? mockApi.triggerSummary(merchantRef, period, idem)
      : request<AgentRunDTO>(`/merchants/${merchantRef}/agent/trigger-summary`, {
          method: 'POST',
          body: period,
          idempotencyKey: idem,
        })
  },

  getRunStatus: (merchantRef: string, runId: string) =>
    USE_MOCK ? mockApi.getRunStatus(merchantRef, runId) : request<AgentRunDTO>(`/merchants/${merchantRef}/agent/runs/${runId}`),

  getRunCost: (merchantRef: string, runId: string) =>
    USE_MOCK ? mockApi.getRunCost(merchantRef, runId) : request<RunCostDTO>(`/merchants/${merchantRef}/agent/runs/${runId}/cost`),

  listNotifications: (merchantRef: string, status = '') => {
    const q = status ? `?status=${status}` : ''
    return USE_MOCK
      ? mockApi.listNotifications(merchantRef, status)
      : request<NotificationDTO[]>(`/merchants/${merchantRef}/notifications${q}`)
  },

  markNotificationRead: (merchantRef: string, id: string) =>
    USE_MOCK
      ? mockApi.markNotificationRead(merchantRef, id)
      : request<NotificationDTO>(`/merchants/${merchantRef}/notifications/${id}/mark-read`, { method: 'POST' }),
}

export default api
export { API_BASE, accessToken, refreshToken }