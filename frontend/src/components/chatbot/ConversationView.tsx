import { widgetClasses, viewClasses, footerClasses } from './layout'
import { cn } from '../../lib/utils'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'
import { ChatHeader } from './ChatHeader'
import type { ChatMessage, ChatUser } from './types'

export interface ConversationViewProps {
  user: ChatUser
  messages: ChatMessage[]
  /** Shows the typing indicator after the last message. UI only: the host owns this state. */
  isAssistantLoading?: boolean
  /** Called with the typed text when the composer is submitted. */
  onSend?: (text: string) => void
  /** Shows the header close button when provided. */
  onMaximize?: () => void
  maximizeDisabled?: boolean
  onClose?: () => void
  /** Shows the header history button when provided. */
  onOpenHistory?: () => void
  /** When true, indicates that the session has timed out due to 5 minutes of inactivity */
  isSessionExpired?: boolean
  /** Action to restart a fresh session when expired */
  onResetSession?: () => void
}

/** Chat state (HiFi node 1:20907). The sidebar is hidden in the HiFi and not implemented. */
export function ConversationView({
  messages,
  isAssistantLoading = false,
  onSend,
  onClose,
  onOpenHistory,
  onMaximize,
  maximizeDisabled,
  isSessionExpired = false,
  onResetSession,
}: ConversationViewProps) {
  return (
    <section
      className={cn(
        'idmc-chatbot idmc-view idmc-conversation',
        widgetClasses,
        viewClasses,
        '[animation:idmc-view-in_var(--idmc-motion-duration-base)_var(--idmc-motion-ease-out)]',
        '[@media(prefers-reduced-motion:_reduce)]:[animation:none]',
      )}
      aria-label="Percakapan"
    >
      <ChatHeader
        title="Chatbot Data Publik"
        onOpenHistory={onOpenHistory}
        onClose={onClose}
        onMaximize={onMaximize}
        maximizeDisabled={maximizeDisabled}
      />
      <MessageList
        messages={messages}
        isAssistantLoading={isAssistantLoading}
        onSendPrompt={onSend}
      />
      <div
        className={cn(
          'idmc-view__footer idmc-conversation__footer',
          footerClasses,
          '[padding-block-start:var(--idmc-content-gap)] short:[padding-block-start:var(--idmc-space-1)]',
        )}
      >
        {isSessionExpired ? (
          <div className="flex flex-col items-center gap-2 w-full py-1">
            <button
              type="button"
              onClick={onResetSession}
              className="w-full py-2.5 px-4 rounded-full bg-[var(--idmc-color-primary-300)] text-[var(--idmc-color-neutral-100)] font-medium text-sm hover:brightness-110 active:scale-[0.98] transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer"
            >
              Mulai Sesi Baru
            </button>
          </div>
        ) : (
          <ChatInput
            variant="chat"
            placeholder="Tanyakan sesuatu..."
            onSubmit={onSend}
            submitDisabled={isAssistantLoading}
            autoFocus
          />
        )}
      </div>
    </section>
  )
}
