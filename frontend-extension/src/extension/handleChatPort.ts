import type { Browser } from 'wxt/browser'
import { requestChatReply } from '../api/chatRequest'
import { ChatServiceUnavailableError, ChatSessionNotFoundError } from '../api/chatTransport'
import { PORTAL_ORIGIN } from '../config/extension'
import { isChatPortRequest, WORKER_REQUEST_TIMEOUT_MS } from './chatProtocol'
import type { ChatPortResponse } from './chatProtocol'

export function isPortalSender(sender: Browser.runtime.MessageSender | undefined, extensionId: string): boolean {
  if (sender?.id !== extensionId || sender.frameId !== 0 || sender.tab?.id === undefined) return false
  try { return new URL(sender.url ?? '').origin === PORTAL_ORIGIN } catch { return false }
}

/** One request per port; disconnect aborts a closing or navigating tab's request. */
export function handleChatPort(port: Browser.runtime.Port, endpoint: string) {
  const controller = new AbortController()
  let handled = false
  port.onDisconnect.addListener(() => {
    const chromeGlobal = (globalThis as unknown as { chrome?: { runtime?: { lastError?: { message?: string } } } }).chrome
    void chromeGlobal?.runtime?.lastError
    controller.abort()
  })
  const respond = (response: ChatPortResponse) => {
    if (controller.signal.aborted) return
    try { port.postMessage(response) } catch { controller.abort() }
  }
  port.onMessage.addListener((value: unknown) => {
    if (handled) return
    handled = true
    if (!isChatPortRequest(value)) { respond({ ok: false, code: 'invalid' }); return }
    if (!endpoint) { respond({ ok: false, code: 'unavailable' }); return }
    void requestChatReply({
      endpoint,
      message: value.message.trim(),
      sessionId: value.sessionId,
      signal: controller.signal,
      timeoutMs: WORKER_REQUEST_TIMEOUT_MS,
    }).then(
      reply => respond({
        ok: true,
        sessionId: reply.sessionId,
        reply: reply.reply,
        replyFormat: reply.replyFormat,
        sources: reply.sources,
      }),
      error => {
        if (error instanceof ChatSessionNotFoundError) respond({ ok: false, code: 'session_not_found' })
        else if (error instanceof ChatServiceUnavailableError) respond({ ok: false, code: 'unavailable' })
        else respond({ ok: false, code: 'failed' })
      },
    )
  })
}
