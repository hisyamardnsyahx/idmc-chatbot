import type { ChatSource } from '../../api/types'

export interface ChatUser {
  name: string
  role: string
  /** Optional avatar image. Falls back to the Figma placeholder avatar. */
  avatarSrc?: string
}

export type MessageRole = 'user' | 'assistant'

/** One row of the History view. */
export interface ChatHistoryItem {
  id: string
  title: string
  /** ISO timestamp when the backend provides it; mock data may omit it. */
  updatedAt?: string
}

export interface ChatMessage {
  id: string
  role: MessageRole
  text: string
  /** Structured citations returned by the backend for assistant replies. */
  sources?: ChatSource[]
  /** Presentation state only; the backend reply contract remains unchanged. */
  status?: 'error'
}

export type { ChatSource }
