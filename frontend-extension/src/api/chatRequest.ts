import { mapSource } from './mapSource'
import { ChatServiceUnavailableError, ChatSessionNotFoundError } from './chatTransport'
import type { ChatReply, ChatSource } from './types'

interface RawChatResponse {
  session_id?: unknown
  reply?: unknown
  reply_format?: unknown
  sources?: unknown
}

interface ErrorBody {
  detail?: unknown
  code?: unknown
  retry_after_s?: unknown
}

export interface ChatRequestOptions {
  endpoint: string
  message: string
  sessionId?: string
  signal?: AbortSignal
  timeoutMs?: number
}

export class ChatRequestError extends Error {
  readonly status: number
  readonly code?: string
  readonly retryAfterS?: number

  constructor(message: string, status: number, code?: string, retryAfterS?: number) {
    super(message)
    this.name = 'ChatRequestError'
    this.status = status
    this.code = code
    this.retryAfterS = retryAfterS
  }
}

async function readRequestError(response: Response): Promise<ChatRequestError> {
  let body: ErrorBody = {}
  try {
    body = (await response.json()) as ErrorBody
  } catch {
    // Non-JSON error bodies are still surfaced through the status code.
  }
  const detail = typeof body.detail === 'string'
    ? body.detail
    : `Chat request failed with status ${response.status}`
  const code = typeof body.code === 'string' ? body.code : undefined
  const retryAfterS = typeof body.retry_after_s === 'number' ? body.retry_after_s : undefined
  return new ChatRequestError(detail, response.status, code, retryAfterS)
}

/** Sends one message and maps the FastAPI response to the shared UI contract. */
export async function requestChatReply({
  endpoint, message, sessionId, signal, timeoutMs = 60_000,
}: ChatRequestOptions): Promise<ChatReply> {
  signal?.throwIfAborted()
  if (!endpoint) throw new ChatServiceUnavailableError()
  const timeout = AbortSignal.timeout(timeoutMs)
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'omit',
    redirect: 'error',
    body: JSON.stringify({
      message,
      ...(sessionId ? { session_id: sessionId } : {}),
    }),
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  })

  if (response.status === 404 && sessionId) throw new ChatSessionNotFoundError()
  if (!response.ok) throw await readRequestError(response)

  const data = (await response.json()) as RawChatResponse
  if (typeof data !== 'object' || data === null ||
    typeof data.reply !== 'string' || !data.reply.trim()) {
    throw new Error('Chat response did not contain a reply')
  }

  const sources = Array.isArray(data.sources)
    ? data.sources
      .map(mapSource)
      .filter((source): source is ChatSource =>
        source !== null && (source.dashboard !== undefined || source.chart !== undefined))
    : []

  return {
    sessionId: typeof data.session_id === 'string' ? data.session_id : '',
    reply: data.reply,
    replyFormat: typeof data.reply_format === 'string' ? data.reply_format : 'markdown',
    sources,
  }
}
