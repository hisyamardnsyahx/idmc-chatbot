import type { ChatHistoryItem, ChatMessage } from './types'

const LOCAL_SESSIONS_KEY = 'idmc_chatbot_local_sessions'
const MAX_LOCAL_SESSIONS = 10

export interface StoredSession {
  id: string
  title: string
  updatedAt: string
  messages: ChatMessage[]
}

function getStorage(): Storage | null {
  if (typeof window !== 'undefined' && window.localStorage) return window.localStorage
  if (typeof globalThis !== 'undefined' && (globalThis as any).localStorage) return (globalThis as any).localStorage
  return null
}

export function getLocalSessions(): StoredSession[] {
  const storage = getStorage()
  if (!storage) return []
  try {
    const raw = storage.getItem(LOCAL_SESSIONS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveLocalSession(session: StoredSession): void {
  const storage = getStorage()
  if (!storage) return
  try {
    const current = getLocalSessions()
    const filtered = current.filter((s) => s.id !== session.id)
    const updated = [session, ...filtered].slice(0, MAX_LOCAL_SESSIONS)
    storage.setItem(LOCAL_SESSIONS_KEY, JSON.stringify(updated))
  } catch {
    // Ignore storage quota or cross-origin restrictions gracefully
  }
}

export function getLocalSessionDetail(sessionId: string): StoredSession | null {
  const all = getLocalSessions()
  return all.find((s) => s.id === sessionId) ?? null
}

export function getLocalSessionSummaries(): ChatHistoryItem[] {
  return getLocalSessions().slice(0, MAX_LOCAL_SESSIONS).map((s) => ({
    id: s.id,
    title: s.title,
    updatedAt: s.updatedAt,
  }))
}

export function clearLocalSessions(): void {
  const storage = getStorage()
  if (!storage) return
  try {
    storage.removeItem(LOCAL_SESSIONS_KEY)
  } catch {
    // Ignore storage failure
  }
}
