export const CHAT_PORT_NAME = 'idmc-chat-v1'
export const MAX_CHAT_MESSAGE_LENGTH = 20_000
export const MAX_SESSION_ID_LENGTH = 64
// Finish before Chromium's 30-second service-worker fetch response limit.
export const WORKER_REQUEST_TIMEOUT_MS = 25_000
export const CLIENT_REQUEST_TIMEOUT_MS = 30_000

const SESSION_ID_PATTERN = /^[A-Za-z0-9_-]+$/

export interface ChatPortRequest {
  type: 'chat'
  message: string
  sessionId?: string
}

export type ChatPortResponse =
  | { ok: true; sessionId: string; reply: string; replyFormat: string; sources: unknown[] }
  | { ok: false; code: 'unavailable' | 'failed' | 'invalid' | 'session_not_found' }

export function isChatPortRequest(value: unknown): value is ChatPortRequest {
  if (typeof value !== 'object' || value === null) return false
  if (!('type' in value) || value.type !== 'chat') return false
  if (!('message' in value) || typeof value.message !== 'string' ||
    value.message.trim().length === 0 || value.message.length > MAX_CHAT_MESSAGE_LENGTH) return false
  if (!('sessionId' in value) || value.sessionId === undefined) return true
  return typeof value.sessionId === 'string' &&
    value.sessionId.length >= 1 && value.sessionId.length <= MAX_SESSION_ID_LENGTH &&
    SESSION_ID_PATTERN.test(value.sessionId)
}

export function isChatPortResponse(value: unknown): value is ChatPortResponse {
  if (typeof value !== 'object' || value === null || !('ok' in value)) return false
  if (value.ok === true) {
    return ('sessionId' in value && typeof value.sessionId === 'string') &&
      ('reply' in value && typeof value.reply === 'string' && !!value.reply.trim()) &&
      ('replyFormat' in value && typeof value.replyFormat === 'string') &&
      ('sources' in value && Array.isArray(value.sources))
  }
  return value.ok === false && 'code' in value &&
    ['unavailable', 'failed', 'invalid', 'session_not_found'].includes(String(value.code))
}
