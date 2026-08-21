import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { authApi, setTokens, ApiError } from '../services/api'

interface AuthState {
  accessToken: string | null
  isAuthenticated: boolean
  loginError: string | null
  isLoggingIn: boolean
  lockoutRetryAfter: number | null
}

const initialState: AuthState = {
  accessToken: null,
  // If a refresh token exists, treat the session as valid so the shell can render
  // and the interceptor can transparently refresh the in-memory access token.
  isAuthenticated: Boolean(localStorage.getItem('zp_refresh')),
  loginError: null,
  isLoggingIn: false,
  lockoutRetryAfter: null,
}

export const login = createAsyncThunk('auth/login', async (credentials: { email: string; password: string }) => {
  const tokens = await authApi.login(credentials.email, credentials.password)
  setTokens(tokens)
  return tokens
})

export const logout = createAsyncThunk('auth/logout', async () => {
  try {
    await authApi.logout()
  } catch {
    // ignore network errors on logout — local state is what matters
  }
  setTokens(null)
})

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(login.pending, (state) => {
        state.isLoggingIn = true
        state.loginError = null
        state.lockoutRetryAfter = null
      })
      .addCase(login.fulfilled, (state, action) => {
        state.isLoggingIn = false
        state.accessToken = action.payload.access
        state.isAuthenticated = true
        state.lockoutRetryAfter = null
      })
      .addCase(login.rejected, (state, action) => {
        state.isLoggingIn = false
        const err = action.error
        const isLocked = (err instanceof ApiError && err.status === 423) || err.message?.includes('LOCKED')
        const isRateLimited = (err instanceof ApiError && err.code === 'RATE_LIMITED') || err.message?.includes('محدودیت نرخ')
        if (isLocked) {
          state.loginError = 'ورود موقتاً برای حفظ امنیت محدود شده است. لطفاً بعداً دوباره تلاش کنید.'
          state.lockoutRetryAfter = (err instanceof ApiError ? err.retryAfterSeconds : undefined) ?? 60
        } else if (isRateLimited) {
          state.loginError = 'محدودیت نرخ — کمی بعد دوباره تلاش کنید'
          state.lockoutRetryAfter = null
        } else {
          state.loginError = 'ایمیل یا رمز عبور نادرست است'
          state.lockoutRetryAfter = null
        }
      })
      .addCase(logout.fulfilled, (state) => {
        state.accessToken = null
        state.isAuthenticated = false
      })
  },
})

export default authSlice.reducer
