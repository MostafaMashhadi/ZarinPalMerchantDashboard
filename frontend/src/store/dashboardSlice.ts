import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import api from '../services/api'
import type { DashboardSummary } from '../services/types'

interface DashboardState {
  summary: DashboardSummary | null
  selectedMerchant: string
  activeTab: string
  isLoading: boolean
  error: string | null
  /** True when the last summary was served from the cached fallback (ClickHouse degraded) */
  degraded: boolean
}

const initialState: DashboardState = {
  summary: null,
  selectedMerchant: 'M18',
  activeTab: 'overview',
  isLoading: false,
  error: null,
  degraded: false,
}

export const fetchDashboardSummary = createAsyncThunk('dashboard/fetchSummary', async (merchantRef: string) => {
  return await api.getDashboardSummary(merchantRef)
})

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState,
  reducers: {
    setSelectedMerchant: (state, action: PayloadAction<string>) => {
      state.selectedMerchant = action.payload
      state.summary = null
    },
    setActiveTab: (state, action: PayloadAction<string>) => {
      state.activeTab = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchDashboardSummary.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchDashboardSummary.fulfilled, (state, action) => {
        state.isLoading = false
        state.summary = action.payload
        state.degraded = action.payload.freshness === 'cached_fallback'
      })
      .addCase(fetchDashboardSummary.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.error.message || 'خطا در دریافت اطلاعات داشبورد'
      })
  },
})

export const { setSelectedMerchant, setActiveTab } = dashboardSlice.actions
export default dashboardSlice.reducer