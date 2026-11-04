/** Client for the FastAPI chat endpoint (`POST /api/chat`). */

import { requestJson } from './client'
import { mapSource } from './mapSource'
import type { ChatReply, ChatSource } from './types'

const CHAT_ENDPOINT = '/api/chat'

interface RawChatResponse {
  session_id?: unknown
  reply?: unknown
  reply_format?: unknown
  sources?: unknown
}

export interface SendChatOptions {
  sessionId?: string
  signal?: AbortSignal
}

/**
 * Sends one message and resolves with the assistant reply plus structured
 * sources. The backend may also return a new session id, which the caller
 * should reuse for subsequent turns.
 */
export async function sendChatMessage(
  message: string,
  options: SendChatOptions = {},
): Promise<ChatReply> {
  const data = await requestJson<RawChatResponse>(
    CHAT_ENDPOINT,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        ...(options.sessionId ? { session_id: options.sessionId } : {}),
      }),
    },
    options.signal,
  )

  if (typeof data.reply !== 'string' || data.reply.trim() === '') {
    throw new Error('Chat response did not contain a reply')
  }

  return {
    sessionId: typeof data.session_id === 'string' ? data.session_id : '',
    reply: data.reply,
    replyFormat: typeof data.reply_format === 'string' ? data.reply_format : 'markdown',
    sources: Array.isArray(data.sources)
      ? data.sources.map(mapSource).filter((source): source is ChatSource => source !== null)
      : [],
  }
}
