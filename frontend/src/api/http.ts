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
  method?: string
  body?: unknown
  headers?: Record<string, string>
  onChunk: (chunk: StreamChunk) => void
  onError?: (error: Error) => void
  onComplete?: () => void
}

export class StreamResponseError extends Error {
  readonly status?: number
  readonly code?: string
  readonly retryAfterSeconds?: number
  constructor(
    message: string,
    status?: number,
    code?: string,
    retryAfterSeconds?: number,
  ) { super(message); this.status = status; this.code = code; this.retryAfterSeconds = retryAfterSeconds }
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
  path: string,
  { mockChunks, mockDelayMs = 120, signal, method = 'POST', body, headers = {}, onChunk, onError, onComplete }: StreamCallOptions,
): Promise<void> {
  try {
    if (mockChunks) {
      for (const chunk of mockChunks) {
        if (signal?.aborted) throw new DOMException('The stream was cancelled.', 'AbortError')
        await new Promise<void>((resolve, reject) => {
          const timeout = window.setTimeout(resolve, mockDelayMs)
          signal?.addEventListener('abort', () => { window.clearTimeout(timeout); reject(new DOMException('The stream was cancelled.', 'AbortError')) }, { once: true })
        })
        onChunk(chunk)
      }
      onComplete?.()
      return
    }

    const response = await fetch(path, {
      method,
      signal,
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream, application/json', ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { error?: string; detail?: string; retry_after_seconds?: number }
      throw new StreamResponseError(payload.detail ?? payload.error ?? `HTTP ${response.status}`, response.status, payload.error, payload.retry_after_seconds)
    }
    // BufferedDelivery returns the same answer payload as one JSON response.
    if (!response.headers.get('content-type')?.includes('text/event-stream')) {
      onChunk({ event: 'buffered', data: JSON.stringify(await response.json()) })
      onComplete?.()
      return
    }
    if (!response.body) throw new Error('پاسخ جریانی قابل خواندن نیست.')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    const emit = (frame: string) => {
      const event = frame.match(/^event:\s*(.+)$/m)?.[1]
      const data = frame.split('\n').filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trimStart()).join('\n')
      if (data) onChunk({ event, data })
    }
    for (;;) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
      const frames = buffer.split(/\r?\n\r?\n/)
      buffer = frames.pop() ?? ''
      frames.forEach(emit)
      if (done) break
    }
    if (buffer.trim()) emit(buffer)
    onComplete?.()
  } catch (cause) {
    const error = cause instanceof Error ? cause : new Error('Unable to read the stream.')
    onError?.(error)
    throw error
  }
}
