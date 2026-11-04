import type { ChatReply } from './types'

export type ChatTransport = (
  message: string,
  options?: { sessionId?: string; signal?: AbortSignal },
) => Promise<ChatReply>

export class ChatServiceUnavailableError extends Error {
  constructor() {
    super('Chat service is not configured')
    this.name = 'ChatServiceUnavailableError'
  }
}

export class ChatSessionNotFoundError extends Error {
  constructor() {
    super('Chat session no longer exists')
    this.name = 'ChatSessionNotFoundError'
  }
}
