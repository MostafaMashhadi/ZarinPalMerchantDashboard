import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import type { Freshness } from '../services/types'

interface UiState {
  dataFreshness: Freshness | null
}

const initialState: UiState = {
  dataFreshness: null,
}

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setDataFreshness: (state, action: PayloadAction<Freshness | null>) => {
      state.dataFreshness = action.payload
    },
  },
})

export const { setDataFreshness } = uiSlice.actions
export default uiSlice.reducer
