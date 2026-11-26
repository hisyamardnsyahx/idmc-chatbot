import { cn } from '../../lib/utils'
import { useEffect, useRef } from 'react'
import type { ChatMessage } from './types'
import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'
import { EmptyState } from './EmptyState'
import { MarkdownContent } from './MarkdownContent'
import { stripSourceBlock } from '../../lib/formatReply'

export interface MessageListProps {
  messages: ChatMessage[]
  label?: string
  /** Renders the typing indicator after the last message. */
  isAssistantLoading?: boolean
  /** Optional handler when a prompt hyperlink is clicked in markdown */
  onSendPrompt?: (prompt: string) => void
  /**
   * Controls whether the list itself acts as an isolated scroll container (used in extension overlay).
   * Set to false in full-page web mode so scrolling belongs strictly to the outer full-width pane.
   */
  containedScroll?: boolean
}

export function MessageList({
  messages,
  label = 'Percakapan',
  isAssistantLoading = false,
  onSendPrompt,
  containedScroll = true,
}: MessageListProps) {
  const listRef = useRef<HTMLUListElement>(null)

  // Keep the newest message (or the typing indicator) in view for contained extension lists.
  useEffect(() => {
    if (!containedScroll) return
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messages, isAssistantLoading, containedScroll])

  return (
    <ul
      ref={listRef}
      className={cn(
        'idmc-message-list',
        'flex flex-col items-stretch [gap:10px] [inline-size:100%]',
        '[min-inline-size:0] [margin:0] [padding:var(--idmc-space-4)_var(--idmc-space-3)]',
        '[background:var(--idmc-color-neutral-100)] [border-radius:var(--idmc-radius-4)] list-none',
        containedScroll &&
          '[flex:1_1_0] [min-block-size:0] overflow-x-hidden overflow-y-auto [overscroll-behavior:contain] [scrollbar-width:thin]',
      )}
      role="log"
      aria-live="polite"
      aria-relevant="additions"
      aria-label={label}
    >
      {messages.length === 0 && !isAssistantLoading && (
        <li>
          <EmptyState message="Belum ada pesan. Mulai dengan pertanyaan tentang data DIY." />
        </li>
      )}
      {messages.map(({ id, role, text, status, sources }) => {
        const hasSources = role === 'assistant' && status !== 'error' && (sources?.length ?? 0) > 0
        // The plain-text sources block is for non-UI clients; cards replace it.
        const body = hasSources ? stripSourceBlock(text) : text
        return (
          <MessageBubble
            key={id}
            role={role}
            status={status}
            sources={role === 'assistant' ? sources : undefined}
          >
            {role === 'assistant' && status !== 'error' ? (
              <MarkdownContent text={body} onSendPrompt={onSendPrompt} />
            ) : (
              <span className={cn('idmc-message__plain-text', 'whitespace-pre-wrap')}>{text}</span>
            )}
          </MessageBubble>
        )
      })}
      {isAssistantLoading && <TypingIndicator />}
    </ul>
  )
}
