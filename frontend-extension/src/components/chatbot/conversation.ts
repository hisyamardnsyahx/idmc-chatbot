import type { ChatMessage } from './types'

export interface SavedConversation {
  id: string
  messages: ChatMessage[]
  updatedAt: number
  title?: string
}

export interface ConversationStore {
  list: () => SavedConversation[] | Promise<SavedConversation[]>
  save: (conversation: SavedConversation) => void | Promise<void>
}

export const CONVERSATION_PREFIX = 'idmc-conversation-v1:'

export function conversationTitle(conversation: SavedConversation) {
  const customTitle = conversation.title
  if (typeof customTitle === 'string' && customTitle.trim()) {
    return customTitle.trim()
  }
  return conversation.messages.find((message) => message.role === 'user')?.text || 'Chat baru'
}

export function isConversation(value: unknown): value is SavedConversation {
  if (!value || typeof value !== 'object') return false
  const record = value as SavedConversation
  return (
    typeof record.id === 'string' &&
    /^[a-zA-Z0-9-]{1,80}$/.test(record.id) &&
    Number.isFinite(record.updatedAt) &&
    (record.title === undefined || typeof record.title === 'string') &&
    Array.isArray(record.messages) &&
    record.messages.every(
      (message) =>
        message &&
        typeof message.id === 'string' &&
        typeof message.text === 'string' &&
        (message.role === 'user' || message.role === 'assistant') &&
        (message.status === undefined || message.status === 'error'),
    ) &&
    new Set(record.messages.map((message) => message.id)).size ===
      record.messages.length
  )
}

export const WELCOME_GREETING_MESSAGE =
  'Selamat datang di **Chatbot Data Publik IDMC Pemda DIY**.\n\n' +
  'Saya dapat membantu Anda menelusuri data dan informasi resmi dari dashboard Pemerintah Daerah DIY, seperti kepegawaian (SIMPEG), realisasi pembangunan, jaringan fiber optic, pemantauan CCTV, IKM, ketahanan pangan, dan lingkungan hidup.\n\n' +
  'Silakan ketik pertanyaan Anda atau pilih salah satu topik rekomendasi di bawah untuk memulai.'

export function createWelcomeMessage(): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role: 'assistant',
    text: WELCOME_GREETING_MESSAGE,
  }
}

export function newConversation(
  messages: ChatMessage[] = [],
): SavedConversation {
  return { id: crypto.randomUUID(), messages, updatedAt: Date.now() }
}

export function newSessionWithWelcome(): SavedConversation {
  return newConversation([createWelcomeMessage()])
}

/** The fragment stays in the browser and is removed as soon as the web app loads. */
export function expandedChatUrl(
  baseUrl: string,
  conversation: SavedConversation,
) {
  const url = new URL(baseUrl)
  if (
    url.protocol !== 'https:' &&
    !(
      url.protocol === 'http:' &&
      ['localhost', '127.0.0.1'].includes(url.hostname)
    )
  ) {
    throw new Error('Alamat web chatbot harus menggunakan HTTPS.')
  }
  url.hash = `conversation=${encodeURIComponent(JSON.stringify(conversation))}`
  if (url.href.length > 1_000_000)
    throw new Error('Percakapan terlalu panjang untuk dibuka di tab baru.')
  return url.href
}
