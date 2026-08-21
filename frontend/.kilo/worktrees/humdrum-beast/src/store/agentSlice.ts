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

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export const startSummary = createAsyncThunk(
  'agent/startSummary',
  async (payload: { merchantRef: string; period: { start: string; end: string } }) => {
    const idemKey = `summary-${payload.merchantRef}-${payload.period.start}`
    const run = await api.triggerSummary(payload.merchantRef, payload.period, idemKey)
    while (true) {
      const status = await api.getRunStatus(payload.merchantRef, run.run_id)
      if (status.status !== 'running') return { run: status, cost: null }
      await sleep(2500)
    }
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
  },
  extraReducers: (builder) => {
    builder
      .addCase(startSummary.pending, (state) => {
        state.generating = true
        state.error = null
        state.cost = null
      })
      .addCase(startSummary.fulfilled, (state, action) => {
        state.generating = false
        state.run = action.payload.run
      })
      .addCase(startSummary.rejected, (state, action) => {
        state.generating = false
        state.error = action.error.message || 'شکست در اجرای خلاصه هوشمند'
      })
      .addCase(fetchRunCost.fulfilled, (state, action) => {
        state.cost = action.payload
      })
  },
})

export const { resetAgent } = agentSlice.actions
export default agentSlice.reducer