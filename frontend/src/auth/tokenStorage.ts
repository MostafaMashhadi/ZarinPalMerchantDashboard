import type { AuthTokens } from '@/services/types'

const refreshKey = 'zp_refresh'
let accessToken: string | null = null

/**
 * Security convention: the short-lived access token is held only in module memory.
 * The refresh token is persisted in localStorage to restore a session after a reload;
 * it is cleared on logout or when refresh fails.
 */
export const tokenStorage = {
  getAccessToken: () => accessToken,
  getRefreshToken: () => localStorage.getItem(refreshKey),
  set(tokens: AuthTokens) {
    accessToken = tokens.access
    localStorage.setItem(refreshKey, tokens.refresh)
  },
  clear() {
    accessToken = null
    localStorage.removeItem(refreshKey)
  },
}
