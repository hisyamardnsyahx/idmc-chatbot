/** Shared API types for the FastAPI backend. */

export interface ChatSource {
  dashboard?: string
  chart?: string
  sliceId?: string | number
  rowsCovered?: string
  dataAsOf?: string
  possiblyOutdated: boolean
  relevance: number
  content: string
}

export interface ChatReply {
  sessionId: string
  reply: string
  replyFormat: string
  sources: ChatSource[]
}

export interface ChatSessionSummary {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  turnCount: number
}

export interface ChatSessionTurn {
  role: 'user' | 'assistant'
  text: string
  sources: ChatSource[]
  at: string
}

export interface ChatSessionDetail extends ChatSessionSummary {
  turns: ChatSessionTurn[]
}
