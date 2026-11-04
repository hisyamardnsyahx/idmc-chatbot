/** Client for the backend session history endpoints. */

import { requestJson } from './client'
import { mapSource } from './mapSource'
import type { ChatSessionDetail, ChatSessionSummary, ChatSessionTurn } from './types'

interface RawSessionSummary {
  id?: unknown
  title?: unknown
  created_at?: unknown
  updated_at?: unknown
  turn_count?: unknown
}

interface RawSessionList {
  sessions?: unknown
}

interface RawSessionDetail extends RawSessionSummary {
  turns?: unknown
}

function mapSummary(raw: RawSessionSummary): ChatSessionSummary | null {
  if (typeof raw.id !== 'string' || raw.id === '') return null
  return {
    id: raw.id,
    title: typeof raw.title === 'string' && raw.title.trim() ? raw.title : 'Chat',
    createdAt: typeof raw.created_at === 'string' ? raw.created_at : '',
    updatedAt: typeof raw.updated_at === 'string' ? raw.updated_at : '',
    turnCount: typeof raw.turn_count === 'number' ? raw.turn_count : 0,
  }
}

function mapTurn(raw: unknown): ChatSessionTurn | null {
  if (typeof raw !== 'object' || raw === null) return null
  const value = raw as {
    role?: unknown
    text?: unknown
    sources?: unknown
    at?: unknown
  }
  if (typeof value.text !== 'string') return null
  return {
    role: value.role === 'user' ? 'user' : 'assistant',
    text: value.text,
    sources: Array.isArray(value.sources)
      ? value.sources.map(mapSource).filter((source) => source !== null)
      : [],
    at: typeof value.at === 'string' ? value.at : '',
  }
}

export async function listSessions(signal?: AbortSignal): Promise<ChatSessionSummary[]> {
  const data = await requestJson<RawSessionList>('/api/sessions', {}, signal)
  if (!Array.isArray(data.sessions)) return []
  return data.sessions
    .filter((raw): raw is RawSessionSummary => typeof raw === 'object' && raw !== null)
    .map(mapSummary)
    .filter((session): session is ChatSessionSummary => session !== null)
}

export async function getSession(
  sessionId: string,
  signal?: AbortSignal,
): Promise<ChatSessionDetail> {
  const data = await requestJson<RawSessionDetail>(
    `/api/sessions/${encodeURIComponent(sessionId)}`,
    {},
    signal,
  )
  const summary = mapSummary(data)
  if (!summary) throw new Error('Session response did not contain an id')
  return {
    ...summary,
    turns: Array.isArray(data.turns)
      ? data.turns.map(mapTurn).filter((turn): turn is ChatSessionTurn => turn !== null)
      : [],
  }
}

export async function deleteSession(sessionId: string): Promise<void> {
  await requestJson<{ deleted?: string }>(
    `/api/sessions/${encodeURIComponent(sessionId)}`,
    { method: 'DELETE' },
  )
}
