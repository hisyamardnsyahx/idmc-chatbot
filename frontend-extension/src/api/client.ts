/** Small fetch wrapper with timeout, JSON parsing and structured errors. */

const REQUEST_TIMEOUT_MS = 60_000

export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly retryAfterS?: number

  constructor(message: string, status: number, code?: string, retryAfterS?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.retryAfterS = retryAfterS
  }
}

interface ErrorBody {
  detail?: unknown
  code?: unknown
  retry_after_s?: unknown
}

async function readError(response: Response): Promise<ApiError> {
  let body: ErrorBody = {}
  try {
    body = (await response.json()) as ErrorBody
  } catch {
    // Non-JSON error bodies are still surfaced through the status code.
  }
  const detail = typeof body.detail === 'string' ? body.detail : `Request failed with status ${response.status}`
  const code = typeof body.code === 'string' ? body.code : undefined
  const retryAfterS = typeof body.retry_after_s === 'number' ? body.retry_after_s : undefined
  return new ApiError(detail, response.status, code, retryAfterS)
}

export async function requestJson<T>(url: string, init: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS)
  const response = await fetch(url, {
    ...init,
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  })

  if (!response.ok) {
    throw await readError(response)
  }

  return (await response.json()) as T
}
