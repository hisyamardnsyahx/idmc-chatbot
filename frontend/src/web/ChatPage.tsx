import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowUpRight,
  BookOpen,
  Check,
  Clock,
  Database,
  HardDrive,
  Lock,
  MapPinOff,
  MessageSquare,
  Pencil,
  Plus,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react'
import idmcIcon from '../assets/figma/idmc-logo.svg'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from '../components/ui/sidebar'
import { ChatInput } from '../components/chatbot/ChatInput'
import { HeroTitle } from '../components/chatbot/HeroTitle'
import { MessageList } from '../components/chatbot/MessageList'
import { SuggestionList } from '../components/chatbot/SuggestionList'
import { widgetClasses } from '../components/chatbot/layout'
import {
  conversationTitle,
  newSessionWithWelcome,
} from '../components/chatbot/conversation'
import type { SavedConversation } from '../components/chatbot/conversation'
import type { ChatMessage, MessageRole } from '../components/chatbot/types'
import {
  INACTIVITY_INSIGHT_MS,
  SESSION_TIMEOUT_MS,
  SESSION_EXPIRED_MESSAGE,
} from '../components/chatbot/ChatOverlay'
import {
  DYNAMIC_INSIGHTS_POOL,
  formatInsightMessage,
  type DynamicInsight,
} from '../components/chatbot/insights'
import {
  CONVERSATION_PREFIX,
  initialConversation,
  readConversations,
} from './conversationStorage'
import { clearAllSessions, deleteSession, getSession, listSessions, renameSession } from '../api/sessionsApi'
import { sendChatMessage } from '../api/chatApi'
import type { ChatReply } from '../api/types'

const suggestions = [
  'Berapa jumlah sentra industri kecil dan menengah (IKM) di DIY?',
  'Data penduduk DIY',
  'Statistik pendidikan',
  'Dashboard Koperasi',
]

const PRIVACY_COMMITMENTS = [
  {
    icon: Database,
    text: 'Pertanyaan Anda hanya digunakan untuk mencari data agregat dan statistik daerah dari dashboard resmi Pemda DIY.',
  },
  {
    icon: MapPinOff,
    text: 'Sistem tidak melacak koordinat GPS perangkat maupun aktivitas penjelajahan Anda di luar chatbot IDMC.',
  },
  {
    icon: HardDrive,
    text: 'Riwayat obrolan tersimpan secara privat di peramban perangkat Anda dan dapat dihapus seutuhnya kapan saja.',
  },
  {
    icon: Clock,
    text: 'Sesi percakapan otomatis diputus jika tidak aktif selama 5 menit untuk menjaga privasi saat perangkat ditinggalkan.',
  },
  {
    icon: Lock,
    text: 'Layanan ini tidak memerlukan pendaftaran akun, kata sandi, maupun kredensial login portal IDMC.',
  },
  {
    icon: BookOpen,
    text: 'Seluruh jawaban bersumber langsung dari basis metadata dan indikator data terbuka Pemerintah Daerah DIY.',
  },
] as const

function PrivacyModal({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  if (!open) return null

  return (
    <div
      className="web-privacy-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="privacy-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="web-privacy-modal">
        <div className="web-privacy-modal-header">
          <div className="web-privacy-header-brand">
            <img src={idmcIcon} alt="" className="web-privacy-header-logo" />
            <div>
              <h2 className="web-privacy-modal-title" id="privacy-modal-title">
                IDMC Menjaga Privasi dan Keamanan Interaksi Anda
              </h2>
              <p className="web-privacy-modal-subtitle">
                Komitmen keterbukaan dan pelindungan data pada Chatbot Data Publik Pemda DIY
              </p>
            </div>
          </div>
          <button
            type="button"
            className="web-privacy-modal-close"
            onClick={onClose}
            aria-label="Tutup kebijakan privasi"
          >
            <X size={18} />
          </button>
        </div>

        <div className="web-privacy-modal-body">
          <div className="web-privacy-hero-card">
            <ShieldCheck size={24} strokeWidth={1.75} className="web-privacy-card-icon" />
            <p>
              <strong>Chatbot tidak meminta, mencatat, atau menyimpan data identitas pribadi Anda</strong> seperti NIK, nama lengkap, alamat rumah, atau nomor telepon.
            </p>
          </div>

          <div className="web-privacy-cards-grid">
            {PRIVACY_COMMITMENTS.map(({ icon: Icon, text }, index) => (
              <div key={index} className="web-privacy-item-card">
                <Icon size={22} strokeWidth={1.75} className="web-privacy-card-icon" />
                <p>{text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="web-privacy-modal-footer">
          <span className="web-privacy-compliance">
            Mengacu pada prinsip pelindungan data pribadi (UU No. 27 Tahun 2022)
          </span>
          <button
            type="button"
            className="web-privacy-modal-dismiss"
            onClick={onClose}
          >
            Mengerti
          </button>
        </div>
      </div>
    </div>
  )
}

function ConfirmClearModal({
  open,
  onConfirm,
  onCancel,
}: {
  open: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  if (!open) return null

  return (
    <div
      className="web-privacy-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="clear-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel()
      }}
    >
      <div className="web-confirm-modal">
        <div className="web-confirm-modal-header">
          <h2 className="web-confirm-modal-title" id="clear-modal-title">
            Hapus Semua Riwayat?
          </h2>
        </div>
        <div className="web-confirm-modal-body">
          <p>
            Semua riwayat percakapan akan dihapus dari peramban dan server. Tindakan ini tidak dapat dibatalkan.
          </p>
        </div>
        <div className="web-confirm-modal-footer">
          <button
            type="button"
            className="web-confirm-btn-cancel"
            onClick={onCancel}
          >
            Batal
          </button>
          <button
            type="button"
            className="web-confirm-btn-danger"
            onClick={onConfirm}
          >
            Hapus Semua
          </button>
        </div>
      </div>
    </div>
  )
}

interface ConversationProps {
  conversation: SavedConversation
  isAssistantLoading: boolean
  onSendMessage: (text: string) => void
  onAppendMessage: (role: MessageRole, text: string) => void
  onResetSession?: () => void
  onOpenPrivacy?: () => void
}

function Conversation({
  conversation,
  isAssistantLoading,
  onSendMessage,
  onAppendMessage,
  onResetSession,
  onOpenPrivacy,
}: ConversationProps) {
  const messages = conversation.messages
  const initialExpired = (() => {
    const last = messages[messages.length - 1]
    return Boolean(last && last.role === 'assistant' && last.text === SESSION_EXPIRED_MESSAGE)
  })()
  const [isSessionExpired, setIsSessionExpired] = useState(initialExpired)
  const isSessionExpiredRef = useRef(initialExpired)
  const lastActivityTimeRef = useRef<number>(Date.now())
  const lastInsightTimeRef = useRef<number>(0)
  const warningSentRef = useRef<boolean>(false)
  const customInsightMsRef = useRef<number | null>(null)
  const customWarningMsRef = useRef<number | null>(null)
  const customTimeoutMsRef = useRef<number | null>(null)
  const conversationRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    isSessionExpiredRef.current = isSessionExpired
  }, [isSessionExpired])

  const recordActivity = useCallback(() => {
    if (isSessionExpiredRef.current) return
    lastActivityTimeRef.current = Date.now()
    lastInsightTimeRef.current = 0
    warningSentRef.current = false
  }, [])

  const handleSendMessage = useCallback(
    (text: string) => {
      recordActivity()
      isSessionExpiredRef.current = false
      setIsSessionExpired(false)
      lastInsightTimeRef.current = 0
      warningSentRef.current = false
      onSendMessage(text)
    },
    [recordActivity, onSendMessage],
  )

  const INSIGHT_STORAGE_KEY = 'idmc_last_insight_idx'

  const getNextInsight = useCallback((): DynamicInsight => {
    let currentIdx = 0
    try {
      if (typeof window !== 'undefined') {
        const raw = window.localStorage.getItem(INSIGHT_STORAGE_KEY)
        if (raw) currentIdx = parseInt(raw, 10) || 0
      }
    } catch {}

    const insight = DYNAMIC_INSIGHTS_POOL[currentIdx % DYNAMIC_INSIGHTS_POOL.length]!
    const nextIdx = (currentIdx + 1) % DYNAMIC_INSIGHTS_POOL.length
    try {
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(INSIGHT_STORAGE_KEY, String(nextIdx))
      }
    } catch {}
    return insight
  }, [])

  const getInactivityInsightMs = useCallback((): number => {
    if (customInsightMsRef.current != null) return customInsightMsRef.current
    if (typeof window !== 'undefined' && (window as any).__IDMC_INSIGHT_MS__) {
      return Number((window as any).__IDMC_INSIGHT_MS__)
    }
    return INACTIVITY_INSIGHT_MS
  }, [])

  const getSessionTimeoutMs = useCallback((): number => {
    if (customTimeoutMsRef.current != null) return customTimeoutMsRef.current
    if (typeof window !== 'undefined' && (window as any).__IDMC_TIMEOUT_MS__) {
      return Number((window as any).__IDMC_TIMEOUT_MS__)
    }
    return SESSION_TIMEOUT_MS
  }, [])

  useEffect(() => {
    lastActivityTimeRef.current = Date.now()
    lastInsightTimeRef.current = 0
    warningSentRef.current = false

    console.info(
      `[IDMC Chatbot Web] Timer Inaktivitas Aktif: Informasi Menarik = ${Math.floor(getInactivityInsightMs() / 1000)}s (2 menit), Peringatan = 240s (4 menit), Putus Sesi = ${Math.floor(getSessionTimeoutMs() / 1000)}s (5 menit).\n` +
      `Panduan Pengujian Cepat di Console:\n` +
      `  - Uji Informasi Menarik: window.postMessage({ type: 'IDMC_TRIGGER_INSIGHT' }, '*')\n` +
      `  - Putus Sesi Seketika: window.postMessage({ type: 'IDMC_TRIGGER_TIMEOUT' }, '*')\n` +
      `  - Mode Uji Cepat (5s info / 10s peringatan / 15s putus): window.postMessage({ type: 'IDMC_SET_FAST_TIMERS' }, '*')\n` +
      `  - Kembalikan ke Standar (2m / 4m / 5m): window.postMessage({ type: 'IDMC_RESET_TIMERS' }, '*')`,
    )

    let lastLoggedSecond = 0

    const checkInactivity = () => {
      if (isSessionExpiredRef.current || isAssistantLoading) {
        return
      }

      const now = Date.now()
      const idleMs = now - lastActivityTimeRef.current
      const insightMs = getInactivityInsightMs()
      const timeoutMs = getSessionTimeoutMs()
      const warningMs =
        customWarningMsRef.current ??
        (timeoutMs > 60_000 ? timeoutMs - 60_000 : Math.floor(timeoutMs * 0.7))
      const idleSec = Math.floor(idleMs / 1000)

      if (idleSec > 0 && idleSec % 30 === 0 && idleSec !== lastLoggedSecond) {
        lastLoggedSecond = idleSec
        console.log(
          `[IDMC Chatbot Web] Waktu idle: ${idleSec}s / ${Math.floor(timeoutMs / 1000)}s (Info: ${Math.floor(insightMs / 1000)}s | Peringatan: ${Math.floor(warningMs / 1000)}s | Putus: ${Math.floor(timeoutMs / 1000)}s)`,
        )
      }

      // Step 3: 5 minutes idle -> Graceful Session Expiration (Sesi Diputus)
      if (idleMs >= timeoutMs) {
        isSessionExpiredRef.current = true
        setIsSessionExpired(true)
        onAppendMessage('assistant', SESSION_EXPIRED_MESSAGE)
        console.warn(
          `[IDMC Chatbot Web] Sesi diputus otomatis setelah ${idleSec}s tidak aktif (Batas: ${Math.floor(timeoutMs / 1000)}s).`,
        )
        return
      }

      // Step 2: 4 minutes idle -> 1-minute warning notice
      if (idleMs >= warningMs && !warningSentRef.current) {
        warningSentRef.current = true
        if (lastInsightTimeRef.current === 0) {
          lastInsightTimeRef.current = now
        }
        onAppendMessage(
          'assistant',
          '**Peringatan Tidak Aktif**\n\n' +
          'Sesi percakapan Anda tidak aktif selama 4 menit. Jika tidak ada aktivitas atau pertanyaan baru, sesi akan diputus otomatis dalam 1 menit.',
        )
        console.info(
          `[IDMC Chatbot Web] Peringatan tidak aktif ditampilkan (${idleSec}s idle).`,
        )
        return
      }

      // Step 1: 2 minutes idle -> Proactive interesting dataset insight
      if (idleMs >= insightMs && lastInsightTimeRef.current === 0) {
        lastInsightTimeRef.current = now
        const insight = getNextInsight()
        onAppendMessage('assistant', formatInsightMessage(insight))
        console.info(
          `[IDMC Chatbot Web] Informasi menarik ditampilkan setelah ${idleSec}s tidak aktif: "${insight.title}".`,
        )
      }
    }

    const intervalId = window.setInterval(checkInactivity, 1_000)

    const handleVisibility = () => {
      if (!document.hidden) {
        checkInactivity()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    window.addEventListener('focus', handleVisibility)

    const handleMessage = (event: MessageEvent) => {
      const data = event.data
      if (!data || typeof data !== 'object') return

      if (data.type === 'IDMC_TRIGGER_INSIGHT') {
        const insight = getNextInsight()
        onAppendMessage('assistant', formatInsightMessage(insight))
        console.info('[IDMC Chatbot Web] Manual Trigger: Wawasan dataset berhasil dimunculkan.')
      } else if (data.type === 'IDMC_TRIGGER_TIMEOUT') {
        isSessionExpiredRef.current = true
        setIsSessionExpired(true)
        onAppendMessage('assistant', SESSION_EXPIRED_MESSAGE)
        console.warn('[IDMC Chatbot Web] Manual Trigger: Sesi diputus berhasil dimunculkan.')
      } else if (data.type === 'IDMC_SET_FAST_TIMERS') {
        customInsightMsRef.current = 5_000
        customWarningMsRef.current = 10_000
        customTimeoutMsRef.current = 15_000
        lastActivityTimeRef.current = Date.now()
        lastInsightTimeRef.current = 0
        warningSentRef.current = false
        console.info('[IDMC Chatbot Web] Mode Uji Cepat Aktif: Informasi = 5s, Peringatan = 10s, Sesi Diputus = 15s.')
      } else if (data.type === 'IDMC_RESET_TIMERS') {
        customInsightMsRef.current = null
        customWarningMsRef.current = null
        customTimeoutMsRef.current = null
        lastActivityTimeRef.current = Date.now()
        lastInsightTimeRef.current = 0
        warningSentRef.current = false
        console.info('[IDMC Chatbot Web] Timers kembali ke standar: Informasi = 120s, Peringatan = 240s, Sesi Diputus = 300s (5 menit).')
      } else if (data.type === 'IDMC_SEND_PROMPT' && typeof data.prompt === 'string') {
        handleSendMessage(data.prompt)
      }
    }
    window.addEventListener('message', handleMessage)

    const handleUserActivity = () => {
      recordActivity()
    }
    window.addEventListener('keydown', handleUserActivity, { passive: true })
    window.addEventListener('pointerdown', handleUserActivity, { passive: true })

    return () => {
      window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', handleVisibility)
      window.removeEventListener('focus', handleVisibility)
      window.removeEventListener('message', handleMessage)
      window.removeEventListener('keydown', handleUserActivity)
      window.removeEventListener('pointerdown', handleUserActivity)
    }
  }, [getInactivityInsightMs, getNextInsight, getSessionTimeoutMs, handleSendMessage, isAssistantLoading, onAppendMessage, recordActivity])

  // Automatically scroll to bottom on new messages or loading states
  useEffect(() => {
    const el = conversationRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, isAssistantLoading])

  const hasMessages = messages.length > 0
  const hasUserMessages = messages.some((m) => m.role === 'user')
  return (
    <div className="web-chat-layout">
      {hasMessages ? (
        <>
          <div className="web-scroll-area" ref={conversationRef}>
            <div className="web-messages-wrapper">
              <MessageList
                messages={messages}
                isAssistantLoading={isAssistantLoading}
                onSendPrompt={handleSendMessage}
                containedScroll={false}
              />
            </div>
          </div>
          <div className="web-composer-wrapper">
            <div className="web-composer">
              {isSessionExpired ? (
                <div className="flex flex-col items-center gap-2 w-full py-1">
                  <button
                    type="button"
                    onClick={onResetSession}
                    className="w-full py-3 px-4 rounded-full bg-[var(--idmc-color-primary-300)] text-[var(--idmc-color-neutral-100)] font-medium text-sm hover:brightness-110 active:scale-[0.98] transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer"
                  >
                    Mulai Sesi Baru
                  </button>
                </div>
              ) : (
                <ChatInput
                  variant="chat"
                  placeholder="Tanyakan sesuatu tentang data DIY..."
                  onSubmit={handleSendMessage}
                  submitDisabled={isAssistantLoading}
                  autoFocus
                />
              )}
              {!hasUserMessages && !isSessionExpired && (
                <SuggestionList items={suggestions} onSelect={handleSendMessage} />
              )}
              {hasUserMessages && !isSessionExpired && (
                <p className="web-composer-note">
                  Periksa kembali jawaban dengan sumber data terkait.
                </p>
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="web-scroll-area web-home-scroll-area" ref={conversationRef}>
          <div className="web-home-container">
            <div className="web-welcome">
              <HeroTitle
                title="Chatbot Data Publik"
                tagline="Jelajahi Data, Kenali Yogyakarta."
              />
              <div className="web-privacy-banner">
                <ShieldCheck size={16} className="text-[var(--idmc-color-primary-500)] flex-shrink-0" />
                <span>Chatbot memproses pertanyaan publik secara anonim tanpa mencatat NIK atau identitas pribadi.</span>
                {onOpenPrivacy && (
                  <button
                    type="button"
                    className="web-privacy-banner-link"
                    onClick={onOpenPrivacy}
                  >
                    Lihat Ketentuan
                  </button>
                )}
              </div>
            </div>
            <div className="web-composer">
              {isSessionExpired ? (
                <div className="flex flex-col items-center gap-2 w-full py-1">
                  <button
                    type="button"
                    onClick={onResetSession}
                    className="w-full py-3 px-4 rounded-full bg-[var(--idmc-color-primary-300)] text-[var(--idmc-color-neutral-100)] font-medium text-sm hover:brightness-110 active:scale-[0.98] transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer"
                  >
                    Mulai Sesi Baru
                  </button>
                </div>
              ) : (
                <ChatInput
                  variant="home"
                  placeholder="Tanyakan sesuatu tentang data DIY..."
                  onSubmit={handleSendMessage}
                  submitDisabled={isAssistantLoading}
                  autoFocus
                />
              )}
              {!isSessionExpired && (
                <SuggestionList items={suggestions} onSelect={handleSendMessage} />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ChatWorkspace() {
  const [initial] = useState(initialConversation)
  const [active, setActive] = useState(initial.conversation)
  const [loadingMap, setLoadingMap] = useState<Record<string, boolean>>({})
  const controllersRef = useRef<Map<string, AbortController>>(new Map())
  const activeRef = useRef(active)
  useEffect(() => {
    activeRef.current = active
  }, [active])

  const [showPrivacyModal, setShowPrivacyModal] = useState(false)
  const [showClearModal, setShowClearModal] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [records, setRecords] = useState<SavedConversation[]>(() => {
    try {
      return readConversations()
    } catch {
      return []
    }
  })
  const [notice, setNotice] = useState(initial.error ?? '')
  const deletedIds = useRef(new Set<string>())
  const { setOpenMobile } = useSidebar()

  useEffect(() => {
    if (window.location.hash.startsWith('#conversation=')) {
      window.history.replaceState(
        null,
        '',
        window.location.pathname + window.location.search,
      )
    }
    const refresh = (event: StorageEvent) => {
      if (event.key === null || event.key.startsWith(CONVERSATION_PREFIX)) {
        try {
          setRecords(readConversations())
        } catch {
          /* Keep the current session usable. */
        }
      }
    }
    window.addEventListener('storage', refresh)
    return () => window.removeEventListener('storage', refresh)
  }, [])

  // Synchronize history with backend sessions
  useEffect(() => {
    listSessions()
      .then((backendSessions) => {
        if (!Array.isArray(backendSessions) || backendSessions.length === 0) return
        setRecords((prev) => {
          const map = new Map<string, SavedConversation>()
          prev.forEach((r) => map.set(r.id, r))
          const merged: SavedConversation[] = [...prev]
          for (const s of backendSessions) {
            if (deletedIds.current.has(s.id)) continue
            const existing = map.get(s.id)
            if (!existing) {
              merged.push({
                id: s.id,
                messages: [],
                updatedAt: s.updatedAt ? new Date(s.updatedAt).getTime() : Date.now(),
                title: s.title,
              })
            } else if (existing.title !== s.title && s.title) {
              existing.title = s.title
            }
          }
          return merged.sort((a, b) => b.updatedAt - a.updatedAt)
        })
      })
      .catch((err) => {
        console.warn('[IDMC Web] Gagal menyinkronkan riwayat dari backend:', err)
      })
  }, [])

  const save = useCallback((conversation: SavedConversation) => {
    if (deletedIds.current.has(conversation.id)) return
    setRecords((previous) => [
      conversation,
      ...previous.filter((item) => item.id !== conversation.id),
    ])
    try {
      localStorage.setItem(
        CONVERSATION_PREFIX + conversation.id,
        JSON.stringify(conversation),
      )
    } catch {
      setNotice(
        'Riwayat belum dapat disimpan di browser ini. Percakapan tetap tersedia selama tab terbuka.',
      )
    }
  }, [])

  const handleSendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed) return
      const currentActive = activeRef.current
      const convId = currentActive.id
      if (loadingMap[convId]) return

      const userMsg: ChatMessage = {
        id:
          typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
            ? crypto.randomUUID()
            : `m_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        role: 'user',
        text: trimmed,
      }

      const existingMsgs = currentActive.messages
      const hasUserMsg = existingMsgs.some((m) => m.role === 'user')
      const newTitle =
        !hasUserMsg && !currentActive.title
          ? trimmed.slice(0, 36) + (trimmed.length > 36 ? '...' : '')
          : currentActive.title

      const updatedMessagesWithUser = [...existingMsgs, userMsg]
      const now = Date.now()

      const updatedConversation: SavedConversation = {
        id: convId,
        messages: updatedMessagesWithUser,
        updatedAt: now,
        title: newTitle,
      }

      save(updatedConversation)
      if (activeRef.current.id === convId) {
        setActive(updatedConversation)
      }

      setLoadingMap((prev) => ({ ...prev, [convId]: true }))

      const controller = new AbortController()
      controllersRef.current.set(convId, controller)

      const doSend = async (): Promise<ChatReply> => {
        try {
          return await sendChatMessage(trimmed, {
            sessionId: convId,
            signal: controller.signal,
          })
        } catch (error) {
          const isNotFound =
            (error as any)?.status === 404 ||
            (error as any)?.code === 'session_not_found'
          if (isNotFound) {
            return await sendChatMessage(trimmed, {
              signal: controller.signal,
            })
          }
          throw error
        }
      }

      doSend()
        .then((reply) => {
          if (deletedIds.current.has(convId)) return

          const assistantMsg: ChatMessage = {
            id:
              typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
                ? crypto.randomUUID()
                : `m_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            role: 'assistant',
            text: reply.reply,
            sources: reply.sources && reply.sources.length > 0 ? reply.sources : undefined,
          }

          setRecords((prev) => {
            const existing = prev.find((r) => r.id === convId)
            const msgs = existing
              ? [...existing.messages, assistantMsg]
              : [...updatedMessagesWithUser, assistantMsg]
            const updated: SavedConversation = {
              id: convId,
              messages: msgs,
              updatedAt: Date.now(),
              title: existing?.title ?? newTitle,
            }
            try {
              localStorage.setItem(CONVERSATION_PREFIX + convId, JSON.stringify(updated))
            } catch {}
            return [updated, ...prev.filter((r) => r.id !== convId)]
          })

          setActive((current) => {
            if (current.id === convId) {
              return {
                ...current,
                messages: [...current.messages, assistantMsg],
                updatedAt: Date.now(),
              }
            }
            return current
          })
        })
        .catch((error) => {
          if (deletedIds.current.has(convId)) return
          if (error instanceof Error && error.name === 'AbortError') return

          const isUnavailable =
            (error as any)?.code === 'SERVICE_UNAVAILABLE' ||
            (error as any)?.status === 503

          const errorMsg: ChatMessage = {
            id:
              typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
                ? crypto.randomUUID()
                : `m_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            role: 'assistant',
            status: 'error',
            text: isUnavailable
              ? 'Layanan chatbot belum tersedia. Silakan coba lagi nanti.'
              : 'Maaf, terjadi kesalahan saat menghubungi server. Silakan coba lagi.',
          }

          setRecords((prev) => {
            const existing = prev.find((r) => r.id === convId)
            const msgs = existing
              ? [...existing.messages, errorMsg]
              : [...updatedMessagesWithUser, errorMsg]
            const updated: SavedConversation = {
              id: convId,
              messages: msgs,
              updatedAt: Date.now(),
              title: existing?.title ?? newTitle,
            }
            try {
              localStorage.setItem(CONVERSATION_PREFIX + convId, JSON.stringify(updated))
            } catch {}
            return [updated, ...prev.filter((r) => r.id !== convId)]
          })

          setActive((current) => {
            if (current.id === convId) {
              return {
                ...current,
                messages: [...current.messages, errorMsg],
                updatedAt: Date.now(),
              }
            }
            return current
          })
        })
        .finally(() => {
          controllersRef.current.delete(convId)
          setLoadingMap((prev) => {
            const copy = { ...prev }
            delete copy[convId]
            return copy
          })
        })
    },
    [loadingMap, save],
  )

  const handleAppendMessage = useCallback(
    (role: MessageRole, text: string) => {
      const currentActive = activeRef.current
      const newMsg: ChatMessage = {
        id:
          typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
            ? crypto.randomUUID()
            : `m_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        role,
        text,
      }
      const updatedMessages = [...currentActive.messages, newMsg]
      const updatedConv: SavedConversation = {
        ...currentActive,
        messages: updatedMessages,
        updatedAt: Date.now(),
      }
      save(updatedConv)
      setActive(updatedConv)
    },
    [save],
  )

  const select = (conversation: SavedConversation) => {
    // Ignore selecting the current row so pending requests keep their lifecycle.
    if (conversation.id !== active.id) {
      if (conversation.messages.length === 0) {
        // Hydrate from backend session
        getSession(conversation.id)
          .then((detail) => {
            const messages: ChatMessage[] = detail.turns.map((t, idx) => ({
              id: `${detail.id}-turn-${idx}`,
              role: t.role,
              text: t.text,
              sources: t.sources,
            }))
            const hydrated: SavedConversation = {
              id: detail.id,
              messages,
              updatedAt: detail.updatedAt ? new Date(detail.updatedAt).getTime() : Date.now(),
              title: detail.title,
            }
            setRecords((prev) =>
              prev.map((r) => (r.id === detail.id ? hydrated : r)),
            )
            try {
              localStorage.setItem(
                CONVERSATION_PREFIX + detail.id,
                JSON.stringify(hydrated),
              )
            } catch {}
            setActive(hydrated)
          })
          .catch(() => {
            setNotice('Gagal memuat percakapan dari server. Membuka percakapan kosong.')
            setActive(conversation)
          })
      } else {
        const fresh = records.find((r) => r.id === conversation.id) ?? conversation
        setActive(fresh)
      }
    }
    setOpenMobile(false)
  }

  const remove = (conversation: SavedConversation) => {
    deletedIds.current.add(conversation.id)
    controllersRef.current.get(conversation.id)?.abort()
    controllersRef.current.delete(conversation.id)
    setLoadingMap((prev) => {
      const next = { ...prev }
      delete next[conversation.id]
      return next
    })
    try {
      localStorage.removeItem(CONVERSATION_PREFIX + conversation.id)
    } catch {
      setNotice('Riwayat gagal dihapus dari penyimpanan browser.')
      return
    }
    setRecords((previous) =>
      previous.filter((item) => item.id !== conversation.id),
    )
    deleteSession(conversation.id).catch(() => {})
    if (active.id === conversation.id) select(newSessionWithWelcome())
  }

  const clearAll = async () => {
    setShowClearModal(false)
    controllersRef.current.forEach((controller, id) => {
      deletedIds.current.add(id)
      controller.abort()
    })
    controllersRef.current.clear()
    setLoadingMap({})

    try {
      const keysToRemove: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(CONVERSATION_PREFIX)) {
          keysToRemove.push(key)
        }
      }
      keysToRemove.forEach((k) => localStorage.removeItem(k))
    } catch {}

    try {
      await clearAllSessions()
    } catch (err) {
      console.warn('[IDMC Web] Gagal menghapus sesi server:', err)
    }

    setRecords([])
    select(newSessionWithWelcome())
  }

  const handleSaveRename = (id: string, newTitle: string) => {
    const trimmed = newTitle.trim()
    setEditingId(null)
    if (!trimmed) return

    setRecords((prev) =>
      prev.map((r) => (r.id === id ? { ...r, title: trimmed } : r)),
    )
    if (active.id === id) {
      setActive((prev) => ({ ...prev, title: trimmed }))
    }
    try {
      const raw = localStorage.getItem(CONVERSATION_PREFIX + id)
      if (raw) {
        const parsed = JSON.parse(raw)
        parsed.title = trimmed
        localStorage.setItem(CONVERSATION_PREFIX + id, JSON.stringify(parsed))
      }
    } catch {}

    renameSession(id, trimmed).catch((err) => {
      console.warn('[IDMC Web] Gagal mengganti nama sesi di server:', err)
    })
  }

  return (
    <>
      <Sidebar>
        <SidebarHeader>
          <a
            className="web-brand"
            href="https://idmc.jogjaprov.go.id/"
            target="_blank"
            rel="noreferrer"
          >
            <img src={idmcIcon} alt="" />
            <span>
              IDMC
              <span className="web-brand-caption">
                Daerah Istimewa Yogyakarta
              </span>
            </span>
          </a>
          <button
            className="web-new-chat"
            type="button"
            onClick={() => select(newSessionWithWelcome())}
          >
            <Plus size={18} />
            Chat baru
          </button>
        </SidebarHeader>
        <SidebarContent>
          <div className="web-history-header">
            <h2 className="web-history-label">Riwayat percakapan</h2>
            {records.length > 0 && (
              <button
                type="button"
                className="web-clear-all-btn"
                onClick={() => setShowClearModal(true)}
                title="Hapus semua riwayat percakapan"
              >
                Hapus semua
              </button>
            )}
          </div>
          {records.length === 0 && (
            <p className="web-empty-history">
              Percakapanmu akan muncul di sini.
            </p>
          )}
          <SidebarMenu>
            {records.map((record) => (
              <SidebarMenuItem key={record.id}>
                {editingId === record.id ? (
                  <div className="web-rename-form">
                    <input
                      type="text"
                      className="web-rename-input"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          handleSaveRename(record.id, editTitle)
                        } else if (e.key === 'Escape') {
                          e.preventDefault()
                          setEditingId(null)
                        }
                      }}
                      autoFocus
                      maxLength={100}
                    />
                    <button
                      type="button"
                      className="web-rename-action web-rename-save"
                      aria-label="Simpan nama"
                      title="Simpan"
                      onClick={() => handleSaveRename(record.id, editTitle)}
                    >
                      <Check size={14} />
                    </button>
                    <button
                      type="button"
                      className="web-rename-action web-rename-cancel"
                      aria-label="Batal ubah nama"
                      title="Batal"
                      onClick={() => setEditingId(null)}
                    >
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <>
                    <SidebarMenuButton
                      isActive={active.id === record.id}
                      onClick={() => select(record)}
                      title={conversationTitle(record)}
                    >
                      <MessageSquare size={16} />
                      <span>{conversationTitle(record)}</span>
                    </SidebarMenuButton>
                    <div className="web-history-actions">
                      <button
                        type="button"
                        className="web-action-btn web-rename-chat"
                        aria-label={`Ubah nama percakapan ${conversationTitle(record)}`}
                        title="Ubah nama"
                        onClick={(e) => {
                          e.stopPropagation()
                          setEditingId(record.id)
                          setEditTitle(conversationTitle(record))
                        }}
                      >
                        <Pencil size={13} />
                      </button>
                      <button
                        type="button"
                        className="web-action-btn web-delete-chat"
                        aria-label={`Hapus percakapan ${conversationTitle(record)}`}
                        title="Hapus"
                        onClick={(e) => {
                          e.stopPropagation()
                          remove(record)
                        }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </>
                )}
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarContent>
        <SidebarFooter>
          <button
            type="button"
            className="web-privacy-btn"
            onClick={() => setShowPrivacyModal(true)}
          >
            <ShieldCheck size={16} />
            <span>Privasi & Transparansi Data</span>
          </button>
          <span className="web-local-note">
            Riwayat tersinkronisasi otomatis
          </span>
          <a
            href="https://idmc.jogjaprov.go.id/"
            target="_blank"
            rel="noreferrer"
          >
            Buka portal IDMC
            <ArrowUpRight size={16} />
          </a>
        </SidebarFooter>
      </Sidebar>
      <main className="web-main">
        <header className="web-header">
          <SidebarTrigger />
          <span>Chatbot Data Publik</span>
        </header>
        {notice && (
          <div className="web-notice" role="status">
            {notice}
            <button type="button" onClick={() => setNotice('')}>
              Tutup
            </button>
          </div>
        )}
        <Conversation
          key={active.id}
          conversation={active}
          isAssistantLoading={Boolean(loadingMap[active.id])}
          onSendMessage={handleSendMessage}
          onAppendMessage={handleAppendMessage}
          onResetSession={() => select(newSessionWithWelcome())}
          onOpenPrivacy={() => setShowPrivacyModal(true)}
        />
      </main>
      <PrivacyModal
        open={showPrivacyModal}
        onClose={() => setShowPrivacyModal(false)}
      />
      <ConfirmClearModal
        open={showClearModal}
        onConfirm={clearAll}
        onCancel={() => setShowClearModal(false)}
      />
    </>
  )
}

export function ChatPage() {
  return (
    <SidebarProvider className={`idmc-chatbot ${widgetClasses}`}>
      <ChatWorkspace />
    </SidebarProvider>
  )
}
