import { requestChatReply } from './chatRequest'
import type { ChatTransport } from './chatTransport'

/** Preview transport backed by the Vite `/api` proxy. */
export const sendChatMessage: ChatTransport = (message, options = {}) =>
  requestChatReply({
    endpoint: '/api/chat',
    message,
    sessionId: options.sessionId,
    signal: options.signal,
  })
