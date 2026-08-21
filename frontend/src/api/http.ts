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

export type StreamChunk = {
  event?: string
  data: string
}

export type StreamCallOptions = {
  /** A mocked sequence keeps the consumer contract stable until the SSE endpoint exists. */
  mockChunks?: StreamChunk[]
  mockDelayMs?: number
  signal?: AbortSignal
  onChunk: (chunk: StreamChunk) => void
  onError?: (error: Error) => void
  onComplete?: () => void
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

/**
 * Streaming seam for the Sprint 3 chat endpoint.
 *
 * In mock mode it emits a deterministic chunk sequence. Once the backend exposes
 * SSE, replace the mock branch with EventSource (or a fetch reader when auth
 * headers are required) without changing any chat component call sites.
 */
export async function streamCall(
  _path: string,
  { mockChunks = [{ event: 'message', data: 'Streaming is ready for Sprint 3.' }], mockDelayMs = 120, signal, onChunk, onError, onComplete }: StreamCallOptions,
): Promise<void> {
  try {
    for (const chunk of mockChunks) {
      if (signal?.aborted) throw new DOMException('The stream was cancelled.', 'AbortError')
      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(resolve, mockDelayMs)
        signal?.addEventListener('abort', () => {
          window.clearTimeout(timeout)
          reject(new DOMException('The stream was cancelled.', 'AbortError'))
        }, { once: true })
      })
      onChunk(chunk)
    }
    onComplete?.()
  } catch (cause) {
    const error = cause instanceof Error ? cause : new Error('Unable to read the stream.')
    onError?.(error)
    throw error
  }
}
