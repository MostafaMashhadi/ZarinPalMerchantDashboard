import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit'
import api from '../services/api'
import type { NotificationDTO, NotificationSeverity } from '../services/types'

interface NotificationsState {
  items: NotificationDTO[]
  loading: boolean
  error: string | null
  open: boolean
}

const initialState: NotificationsState = {
  items: [],
  loading: false,
  error: null,
  open: false,
}

export const fetchNotifications = createAsyncThunk('notifications/fetch', async (merchantRef: string) => {
  return await api.listNotifications(merchantRef)
})

export const markNotificationRead = createAsyncThunk(
  'notifications/markRead',
  async (payload: { merchantRef: string; id: string }, { dispatch }) => {
    await api.markNotificationRead(payload.merchantRef, payload.id)
    await dispatch(fetchNotifications(payload.merchantRef))
    return payload.id
  },
)
const notificationsSlice = createSlice({
  name: 'notifications',
  initialState,
  reducers: {
    setOpen: (state, action) => {
      state.open = action.payload
    },
    markReadLocal: (state, action: PayloadAction<string>) => {
      const item = state.items.find((n) => n.id === action.payload)
      if (item) {
        item.read_at = new Date().toISOString()
      }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchNotifications.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchNotifications.fulfilled, (state, action) => {
        state.loading = false
        state.items = action.payload
      })
      .addCase(fetchNotifications.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'خطا در دریافت اعلان‌ها'
      })
  },
})

export const unreadCount = (list: NotificationDTO[]): number => list.filter((n) => n.read_at === null).length

export const severityColor = (severity: NotificationSeverity): string => {
  switch (severity) {
    case 'critical':
      return 'border-destructive/20 bg-destructive/10 text-destructive'
    case 'warning':
      return 'border-gold/20 bg-gold/10 text-gold-deep'
    default:
      return 'border-primary/20 bg-primary/10 text-primary'
  }
}

export const { setOpen, markReadLocal } = notificationsSlice.actions
export default notificationsSlice.reducer