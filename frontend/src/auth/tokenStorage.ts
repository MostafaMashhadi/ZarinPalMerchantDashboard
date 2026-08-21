import type { AuthTokens } from '@/services/types'

const refreshKey = 'zp_refresh'
let accessToken: string | null = null

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
