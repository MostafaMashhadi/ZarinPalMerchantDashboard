import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import api from '../services/api'
import type { AnalysisParams, InsightDTO, InsightFilters, InsightKind, Page, ProvenanceEntry } from '../services/types'

interface InsightsState {
  filters: InsightFilters
  page: InsightDTO[]
  total: number
  currentPage: number
  pageSize: number
  loading: boolean
  error: string | null
  detail: InsightDTO | null
  provenance: ProvenanceEntry[] | null
  detailLoading: boolean
  detailError: string | null
  runningKind: InsightKind | null
  runningError: string | null
}

const initialState: InsightsState = {
  filters: {},
  page: [],
  total: 0,
  currentPage: 1,
  pageSize: 6,
  loading: false,
  error: null,
  detail: null,
  provenance: null,
  detailLoading: false,
  detailError: null,
  runningKind: null,
  runningError: null,
}

export const fetchInsights = createAsyncThunk(
  'insights/fetchList',
  async (merchantRef: string, { getState }) => {
    const state = getState() as { insights: InsightsState }
    const { filters, currentPage, pageSize } = state.insights
    return await api.listInsights(merchantRef, { ...filters, page: currentPage, page_size: pageSize })
  },
)

export const fetchInsightDetail = createAsyncThunk(
  'insights/fetchDetail',
  async (payload: { merchantRef: string; insightId: string }) => {
    const detail = await api.getInsight(payload.merchantRef, payload.insightId)
    let provenance: ProvenanceEntry[]
    try {
      provenance = await api.getInsightProvenance(payload.merchantRef, payload.insightId)
    } catch {
      provenance = []
    }
    return { detail, provenance }
  },
)

export const runAnalysis = createAsyncThunk(
  'insights/runAnalysis',
  async (payload: { merchantRef: string; kind: InsightKind; params: AnalysisParams }, { dispatch }) => {
    const created = await api.runAnalysis(payload.merchantRef, payload.kind, payload.params)
    await dispatch(fetchInsights(payload.merchantRef))
    return created
  },
)

const insightsSlice = createSlice({
  name: 'insights',
  initialState,
  reducers: {
    setKindFilter: (state, action: PayloadAction<InsightKind | ''>) => {
      state.filters.kind = action.payload
      state.currentPage = 1
    },
    setPage: (state, action: PayloadAction<number>) => {
      state.currentPage = action.payload
    },
    clearDetail: (state) => {
      state.detail = null
      state.provenance = null
      state.detailError = null
    },
    resetInsights: (state) => {
      state.filters = {}
      state.page = []
      state.total = 0
      state.currentPage = 1
      state.detail = null
      state.provenance = null
      state.detailError = null
      state.detailLoading = false
      state.runningKind = null
      state.runningError = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchInsights.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchInsights.fulfilled, (state, action: PayloadAction<Page<InsightDTO>>) => {
        state.loading = false
        state.page = action.payload.items
        state.total = action.payload.total
        state.currentPage = action.payload.page
      })
      .addCase(fetchInsights.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'خطا در دریافت بینش‌ها'
      })
      .addCase(fetchInsightDetail.pending, (state) => {
        state.detailLoading = true
        state.detailError = null
      })
      .addCase(fetchInsightDetail.fulfilled, (state, action) => {
        state.detailLoading = false
        state.detail = action.payload.detail
        state.provenance = action.payload.provenance
      })
      .addCase(fetchInsightDetail.rejected, (state, action) => {
        state.detailLoading = false
        state.detailError = action.error.message || 'خطا در دریافت جزئیات بینش'
      })
      .addCase(runAnalysis.pending, (state, action) => {
        state.runningKind = action.meta.arg.kind
        state.runningError = null
      })
      .addCase(runAnalysis.fulfilled, (state) => {
        state.runningKind = null
      })
      .addCase(runAnalysis.rejected, (state, action) => {
        state.runningKind = null
        state.runningError = action.error.message || 'خطا در اجرای تحلیل'
      })
  },
})

export const { setKindFilter, setPage, clearDetail, resetInsights } = insightsSlice.actions
export default insightsSlice.reducer