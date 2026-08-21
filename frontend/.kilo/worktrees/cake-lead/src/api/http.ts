export function mockSuccess<T>(data: T, delayMs = 300): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(data), delayMs))
}

export function mockError(message: string, delayMs = 300): Promise<never> {
  return new Promise((_, reject) => setTimeout(() => reject(new Error(message)), delayMs))
}

export type ApiCallOptions = {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  idempotencyKey?: string
}

export async function apiCall<T>(
  path: string,
  options: ApiCallOptions = {},
): Promise<T> {
  const { method = 'GET', body, headers = {}, idempotencyKey } = options
  const finalHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers,
  }
  if (idempotencyKey) finalHeaders['Idempotency-Key'] = idempotencyKey

  const resp = await fetch(path, {
    method,
    headers: finalHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    let errorMessage = `HTTP ${resp.status}`
    try {
      const data = JSON.parse(text)
      errorMessage = data.detail ?? data.error ?? data.message ?? errorMessage
    } catch {
      if (text) errorMessage = text
    }
    throw new Error(errorMessage)
  }

  return resp.json() as Promise<T>
}
