import { useCallback, useEffect, useRef, useState } from 'react'
import { sendChatMessage } from '../../api/chatApi'
import { ChatServiceUnavailableError, ChatSessionNotFoundError } from '../../api/chatTransport'
import type { ChatTransport } from '../../api/chatTransport'
import { getSession } from '../../api/sessionsApi'
import type { ChatReply, ChatSource } from '../../api/types'
import type { ChatMessage, MessageRole } from './types'
import { getLocalSessionDetail, saveLocalSession } from './localHistory'

const CHAT_ERROR_MESSAGE =
  'Maaf, terjadi kesalahan saat menghubungi server. Silakan coba lagi.'

/**
 * Owns one conversation. The session id is reused for every turn, so the
 * backend can persist history. Closing the overlay resets the local view; the
 * server-side session remains available from the History view.
 */
export function useChatSession(requestReply: ChatTransport = sendChatMessage) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isAssistantLoading, setIsAssistantLoading] = useState(false)
  const [isHydrating, setIsHydrating] = useState(false)
  const nextMessageId = useRef(0)
  const requestRef = useRef<AbortController | null>(null)

  const appendMessage = useCallback(
    (role: MessageRole, text: string, status?: 'error', sources?: ChatSource[]) => {
      const id = `m${nextMessageId.current++}`
      setMessages((previous) => [
        ...previous,
        { id, role, text, status, sources },
      ])
    },
    [],
  )

  const resetConversation = useCallback(() => {
    requestRef.current?.abort()
    requestRef.current = null
    setIsAssistantLoading(false)
    setIsHydrating(false)
    setSessionId(null)
    setMessages([])
    nextMessageId.current = 0
  }, [])

  const sendMessage = useCallback(
    async (value: string) => {
      const text = value.trim()
      // A synchronous ref guard also blocks two submits before React rerenders.
      if (!text || requestRef.current) return
      const controller = new AbortController()
      requestRef.current = controller
      appendMessage('user', text)
      setIsAssistantLoading(true)

      try {
        let reply: ChatReply
        try {
          reply = await requestReply(text, {
            sessionId: sessionId ?? undefined,
            signal: controller.signal,
          })
        } catch (error) {
          // A session may have been deleted server-side. Start a fresh one
          // instead of dead-ending the conversation.
          if (sessionId && error instanceof ChatSessionNotFoundError) {
            setSessionId(null)
            reply = await requestReply(text, { signal: controller.signal })
          } else {
            throw error
          }
        }

        if (!controller.signal.aborted) {
          if (reply.sessionId) setSessionId(reply.sessionId)
          appendMessage('assistant', reply.reply, undefined, reply.sources)
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          if (error instanceof Error && error.name === 'AbortError') return
          appendMessage(
            'assistant',
            // The extension keeps its "service not configured" wording.
            error instanceof ChatServiceUnavailableError
              ? 'Layanan chatbot belum tersedia. Silakan coba lagi nanti.'
              : CHAT_ERROR_MESSAGE,
            'error',
          )
        }
      } finally {
        if (requestRef.current === controller) {
          requestRef.current = null
          setIsAssistantLoading(false)
        }
      }
    },
    [appendMessage, sessionId, requestReply],
  )

  const loadSession = useCallback(async (id: string) => {
    requestRef.current?.abort()
    requestRef.current = null
    setIsAssistantLoading(false)
    setIsHydrating(true)
    try {
      try {
        const session = await getSession(id)
        setSessionId(session.id)
        nextMessageId.current = session.turns.length
        setMessages(
          session.turns.map((turn, index) => ({
            id: `s${index}`,
            role: turn.role,
            text: turn.text,
            sources: turn.role === 'assistant' && turn.sources.length > 0 ? turn.sources : undefined,
          })),
        )
        return
      } catch (error) {
        const local = getLocalSessionDetail(id)
        if (local && local.messages.length > 0) {
          setSessionId(local.id)
          nextMessageId.current = local.messages.length
          setMessages(local.messages)
          return
        }
        throw error
      }
    } finally {
      setIsHydrating(false)
    }
  }, [])

  // Auto-save conversation to local storage so history works offline & in extension
  useEffect(() => {
    if (messages.length === 0) return
    const sid = sessionId || 'sess_current'
    const firstUser = messages.find((m) => m.role === 'user')
    const title = firstUser
      ? firstUser.text.slice(0, 36) + (firstUser.text.length > 36 ? '...' : '')
      : 'Percakapan IDMC'
    saveLocalSession({
      id: sid,
      title,
      updatedAt: new Date().toISOString(),
      messages,
    })
  }, [messages, sessionId])

  useEffect(() => () => requestRef.current?.abort(), [])

  return {
    messages,
    sessionId,
    isAssistantLoading,
    isHydrating,
    sendMessage,
    loadSession,
    resetConversation,
    appendMessage,
  }
}
