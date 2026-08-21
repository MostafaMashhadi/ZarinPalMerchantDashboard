import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../services/api'
import type { AgentRunDTO, RunCostDTO } from '../services/types'

interface AgentState {
  generating: boolean
  run: AgentRunDTO | null
  cost: RunCostDTO | null
  error: string | null
}

const initialState: AgentState = {
  generating: false,
  run: null,
  cost: null,
  error: null,
}

export const triggerSummary = createAsyncThunk(
  'agent/triggerSummary',
  async (payload: { merchantRef: string; period: { start: string; end: string }; idemKey: string }) => {
    return await api.triggerSummary(payload.merchantRef, payload.period, payload.idemKey)
  },
)

export const pollRunStatus = createAsyncThunk(
  'agent/pollRunStatus',
  async (payload: { merchantRef: string; runId: string }) => {
    return await api.getRunStatus(payload.merchantRef, payload.runId)
  },
)

export const fetchRunCost = createAsyncThunk('agent/fetchCost', async (payload: { merchantRef: string; runId: string }) => {
  return await api.getRunCost(payload.merchantRef, payload.runId)
})

const agentSlice = createSlice({
  name: 'agent',
  initialState,
  reducers: {
    resetAgent: (state) => {
      state.generating = false
      state.run = null
      state.cost = null
      state.error = null
    },
    setError: (state, action) => {
      state.error = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(triggerSummary.pending, (state) => {
        state.generating = true
        state.error = null
        state.cost = null
        state.run = null
      })
      .addCase(triggerSummary.fulfilled, (state, action) => {
        state.generating = false
        state.run = action.payload
      })
      .addCase(triggerSummary.rejected, (state, action) => {
        state.generating = false
        state.error = action.error.message || 'شکست در اجرای خلاصه هوشمند'
      })
      .addCase(pollRunStatus.fulfilled, (state, action) => {
        state.run = action.payload
        if (action.payload.status !== 'running') {
          state.generating = false
        }
      })
      .addCase(pollRunStatus.rejected, (state, action) => {
        state.generating = false
        state.error = action.error.message || 'شکست در به‌روزرسانی وضعیت اجرا'
      })
      .addCase(fetchRunCost.fulfilled, (state, action) => {
        state.cost = action.payload
      })
  },
})

export const { resetAgent, setError } = agentSlice.actions
export default agentSlice.reducer