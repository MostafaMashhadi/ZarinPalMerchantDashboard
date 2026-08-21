import { tokenStorage } from './tokenStorage'

/** Refreshes an expired session once. A failed refresh clears all local session state. */
export async function refreshAccessToken(apiBase: string): Promise<boolean> {
  const refresh = tokenStorage.getRefreshToken()
  if (!refresh) return false

  try {
    const response = await fetch(`${apiBase}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    })
    if (!response.ok) throw new Error('Refresh failed')

    const data = (await response.json()) as { access: string }
    tokenStorage.set({ access: data.access, refresh })
    return true
  } catch {
    tokenStorage.clear()
    window.dispatchEvent(new CustomEvent('auth:logout'))
    if (window.location.pathname !== '/login') window.location.assign('/login')
    return false
  }
}

/** Replays the original request at most once after a successful silent refresh. */
export async function withSilentRefresh<T>(request: (retry: boolean) => Promise<T>, apiBase: string): Promise<T> {
  try {
    return await request(false)
  } catch (error) {
    if (!(error instanceof Response) || error.status !== 401 || !(await refreshAccessToken(apiBase))) throw error
    return request(true)
  }
}
