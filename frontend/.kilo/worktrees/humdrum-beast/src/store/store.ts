import { configureStore } from '@reduxjs/toolkit'
import dashboardReducer from './dashboardSlice'
import insightsReducer from './insightsSlice'
import agentReducer from './agentSlice'
import notificationsReducer from './notificationsSlice'
import authReducer from './authSlice'
import uiReducer from './uiSlice'

export const store = configureStore({
  reducer: {
    dashboard: dashboardReducer,
    insights: insightsReducer,
    agent: agentReducer,
    notifications: notificationsReducer,
    auth: authReducer,
    ui: uiReducer,
  },
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch