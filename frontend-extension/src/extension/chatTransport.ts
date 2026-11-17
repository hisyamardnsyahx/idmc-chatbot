import { browser } from 'wxt/browser'
import {
  ChatServiceUnavailableError,
  ChatSessionNotFoundError,
} from '../api/chatTransport'
import type { ChatTransport } from '../api/chatTransport'
import type { ChatReply, ChatSource } from '../api/types'
import { CHAT_PORT_NAME, CLIENT_REQUEST_TIMEOUT_MS, isChatPortResponse } from './chatProtocol'

function sendOnce(
  message: string,
  sessionId?: string,
  signal?: AbortSignal,
): Promise<ChatReply> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(signal.reason); return }
    let port: ReturnType<typeof browser.runtime.connect>
    try {
      port = browser.runtime.connect({ name: CHAT_PORT_NAME })
      // Clear any initial connection error flag on native chrome
      void (globalThis as unknown as { chrome?: { runtime?: { lastError?: unknown } } }).chrome?.runtime?.lastError
    } catch (connectError) {
      reject(connectError instanceof Error ? connectError : new Error('Gagal menghubungkan ke ekstensi'))
      return
    }
    let settled = false
    const finish = (error?: unknown, reply?: ChatReply) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      signal?.removeEventListener('abort', onAbort)
      try { port.disconnect() } catch { /* An invalidated extension is already disconnected. */ }
      if (error) reject(error)
      else resolve(reply!)
    }
    const onAbort = () => finish(signal?.reason ?? new DOMException('Aborted', 'AbortError'))
    const timeout = setTimeout(() => finish(new Error('Chat response timed out')), CLIENT_REQUEST_TIMEOUT_MS)
    signal?.addEventListener('abort', onAbort, { once: true })
    port.onDisconnect.addListener(() => {
      // Access chrome.runtime.lastError directly so Chromium marks it as checked
      const chromeGlobal = (globalThis as unknown as { chrome?: { runtime?: { lastError?: { message?: string } } } }).chrome
      const chromeErr = chromeGlobal?.runtime?.lastError
      const browserErr = browser.runtime.lastError
      const errMessage = chromeErr?.message ?? browserErr?.message ?? 'Chat service disconnected'
      finish(new Error(errMessage))
    })
    port.onMessage.addListener((value: unknown) => {
      if (!isChatPortResponse(value)) { finish(new Error('Invalid chat response')); return }
      if (value.ok) {
        finish(undefined, {
          sessionId: value.sessionId,
          reply: value.reply,
          replyFormat: value.replyFormat,
          sources: value.sources as ChatSource[],
        })
      } else if (value.code === 'unavailable') finish(new ChatServiceUnavailableError())
      else if (value.code === 'session_not_found') finish(new ChatSessionNotFoundError())
      else finish(new Error('Chat request failed'))
    })
    const request = sessionId
      ? { type: 'chat' as const, message, sessionId }
      : { type: 'chat' as const, message }
    try { port.postMessage(request) } catch (error) { finish(error) }
  })
}

export const sendExtensionChatMessage: ChatTransport = async (message, options = {}) => {
  const { sessionId, signal } = options
  if (signal?.aborted) throw signal.reason

  const maxRetries = 2
  let lastError: unknown = new Error('Chat service disconnected')

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    if (signal?.aborted) throw signal.reason
    try {
      return await sendOnce(message, sessionId, signal)
    } catch (err) {
      lastError = err
      // Never retry if service is unconfigured or session expired
      if (err instanceof ChatServiceUnavailableError || err instanceof ChatSessionNotFoundError) {
        throw err
      }
      const errMsg = err instanceof Error ? err.message : String(err)
      const isConnectionDrop =
        errMsg.includes('disconnected') ||
        errMsg.includes('Receiving end does not exist') ||
        errMsg.includes('Could not establish connection') ||
        errMsg.includes('closed before a response')

      // If service worker was dormant/asleep, wait for it to wake up and retry
      if (isConnectionDrop && attempt < maxRetries && !signal?.aborted) {
        await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)))
        continue
      }
      throw err
    }
  }
  throw lastError
}
