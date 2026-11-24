import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowUpRight,
  CheckCircle2,
  MessageSquare,
  Plus,
  ShieldCheck,
  Trash2,
  X,
  XCircle,
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
import { useChatSession } from '../components/chatbot/useChatSession'
import { conversationTitle, newConversation } from '../components/chatbot/conversation'
import type { SavedConversation } from '../components/chatbot/conversation'
import type { ChatMessage } from '../components/chatbot/types'
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
import { deleteSession, getSession, listSessions } from '../api/sessionsApi'

const suggestions = [
  'Berapa jumlah sentra industri kecil dan menengah (IKM) di DIY?',
  'Data penduduk DIY',
  'Statistik pendidikan',
  'Dashboard Koperasi',
]

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
          <div>
            <div className="web-privacy-modal-title" id="privacy-modal-title">
              <ShieldCheck size={22} className="text-[var(--idmc-color-primary-500)]" />
              <span>Transparansi & Kebijakan Data</span>
            </div>
            <p className="web-privacy-modal-subtitle">
              Kepatuhan UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi (PDP)
            </p>
          </div>
          <button
            type="button"
            className="web-privacy-modal-close"
            onClick={onClose}
            aria-label="Tutup kebijakan privasi"
          >
            <X size={20} />
          </button>
        </div>

        <div className="web-privacy-modal-body">
          <div className="web-privacy-grid">
            <div className="web-privacy-card web-privacy-card-recorded">
              <div className="web-privacy-card-header">
                <CheckCircle2 size={18} />
                <span>Data yang DICATAT</span>
              </div>
              <ul className="web-privacy-list">
                <li>
                  <span>• <strong>Pertanyaan & Jawaban:</strong> Diproses secara anonim untuk penjawaban data agregat daerah.</span>
                </li>
                <li>
                  <span>• <strong>ID Sesi Anonim:</strong> Token sesi acak sementara untuk mengelompokkan percakapan saat aktif.</span>
                </li>
                <li>
                  <span>• <strong>Waktu Interaksi:</strong> Stempel waktu (timestamp) untuk mengurutkan riwayat percakapan.</span>
                </li>
                <li>
                  <span>• <strong>Riwayat Browser:</strong> Disimpan di peramban Anda (localStorage) agar Anda dapat melanjutkannya.</span>
                </li>
              </ul>
            </div>

            <div className="web-privacy-card web-privacy-card-not-recorded">
              <div className="web-privacy-card-header">
                <XCircle size={18} />
                <span>Data yang TIDAK Dicatat</span>
              </div>
              <ul className="web-privacy-list">
                <li>
                  <span>• <strong>Identitas Pribadi (PII):</strong> Nama lengkap, NIK, alamat rumah, nomor HP, atau email.</span>
                </li>
                <li>
                  <span>• <strong>Kredensial & Sandi:</strong> Password, kata sandi, atau token autentikasi akun IDMC.</span>
                </li>
                <li>
                  <span>• <strong>Lokasi Presisi:</strong> Koordinat GPS perangkat atau pelacakan IP address perorangan.</span>
                </li>
                <li>
                  <span>• <strong>Aktivitas Web Lain:</strong> Riwayat penjelajahan tab atau situs lain di luar chatbot IDMC.</span>
                </li>
              </ul>
            </div>
          </div>

          <div className="web-privacy-legal">
            <strong>Prinsip Minimasi Data:</strong> Layanan chatbot IDMC Pemda DIY beroperasi secara tertutup pada basis pengetahuan agregat data publik (RAG). Tidak ada profil pengguna perorangan yang dibentuk atau diperjualbelikan.
          </div>
        </div>

        <div className="web-privacy-modal-footer">
          <button
            type="button"
            className="web-privacy-modal-dismiss"
            onClick={onClose}
          >
            Mengerti & Tutup
          </button>
        </div>
      </div>
    </div>
  )
}

function Conversation({
  conversation,
  onSave,
  onResetSession,
  onOpenPrivacy,
}: {
  conversation: SavedConversation
  onSave: (conversation: SavedConversation) => void
  onResetSession?: () => void
  onOpenPrivacy?: () => void
}) {
  const { messages, isAssistantLoading, sendMessage, appendMessage } = useChatSession(
    undefined,
    conversation.messages,
    conversation.id,
  )
  const [isSessionExpired, setIsSessionExpired] = useState(false)
  const isSessionExpiredRef = useRef(false)
  const lastActivityTimeRef = useRef<number>(Date.now())
  const lastInsightTimeRef = useRef<number>(0)
  const customInsightMsRef = useRef<number | null>(null)
  const customTimeoutMsRef = useRef<number | null>(null)
  const conversationRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    isSessionExpiredRef.current = isSessionExpired
  }, [isSessionExpired])

  const recordActivity = useCallback(() => {
    if (isSessionExpiredRef.current) return
    lastActivityTimeRef.current = Date.now()
    lastInsightTimeRef.current = 0
  }, [])

  const handleSendMessage = useCallback(
    (text: string) => {
      recordActivity()
      isSessionExpiredRef.current = false
      setIsSessionExpired(false)
      void sendMessage(text)
    },
    [recordActivity, sendMessage],
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

    console.info(
      `[IDMC Chatbot Web] Mesin Idle Aktif: Tier 1 Insight = ${Math.floor(getInactivityInsightMs() / 1000)}s, Tier 2 Timeout = ${Math.floor(getSessionTimeoutMs() / 1000)}s.\n` +
      `Panduan Pengujian Cepat di Console:\n` +
      `  - Uji Wawasan Instan: window.postMessage({ type: 'IDMC_TRIGGER_INSIGHT' }, '*')\n` +
      `  - Uji Selesai Sesi Instan: window.postMessage({ type: 'IDMC_TRIGGER_TIMEOUT' }, '*')\n` +
      `  - Mode Cepat (10s/25s): window.postMessage({ type: 'IDMC_SET_FAST_TIMERS' }, '*')`,
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
      const idleSec = Math.floor(idleMs / 1000)

      if (idleSec > 0 && idleSec % 30 === 0 && idleSec !== lastLoggedSecond) {
        lastLoggedSecond = idleSec
        console.log(`[IDMC Chatbot Web] Waktu idle: ${idleSec}s (Target Insight: ${Math.floor(insightMs / 1000)}s | Target Timeout: ${Math.floor(timeoutMs / 1000)}s)`)
      }

      // Tier 2: 5 minutes idle -> Graceful Session Expiration
      if (idleMs >= timeoutMs) {
        isSessionExpiredRef.current = true
        setIsSessionExpired(true)
        appendMessage('assistant', SESSION_EXPIRED_MESSAGE)
        console.warn(`[IDMC Chatbot Web] Tier 2 Trigger: Sesi ditutup otomatis setelah ${idleSec}s tidak aktif (AWS Lex/OWASP benchmark).`)
        return
      }

      // Tier 1: 2 minutes idle -> Proactive Dynamic Rotating Insight
      if (idleMs >= insightMs) {
        const msSinceLastInsight = now - lastInsightTimeRef.current
        if (lastInsightTimeRef.current === 0 || msSinceLastInsight >= insightMs) {
          lastInsightTimeRef.current = now
          const insight = getNextInsight()
          appendMessage('assistant', formatInsightMessage(insight))
          console.info(`[IDMC Chatbot Web] Tier 1 Trigger: Wawasan dataset ditampilkan (${idleSec}s idle): "${insight.title}"`)
        }
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
        appendMessage('assistant', formatInsightMessage(insight))
        console.info('[IDMC Chatbot Web] Manual Trigger: Wawasan dataset berhasil dimunculkan.')
      } else if (data.type === 'IDMC_TRIGGER_TIMEOUT') {
        isSessionExpiredRef.current = true
        setIsSessionExpired(true)
        appendMessage('assistant', SESSION_EXPIRED_MESSAGE)
        console.warn('[IDMC Chatbot Web] Manual Trigger: Sesi expired berhasil dimunculkan.')
      } else if (data.type === 'IDMC_SET_FAST_TIMERS') {
        customInsightMsRef.current = 10_000
        customTimeoutMsRef.current = 25_000
        lastActivityTimeRef.current = Date.now()
        lastInsightTimeRef.current = 0
        console.info('[IDMC Chatbot Web] Fast timers aktif: Insight = 10s, Timeout = 25s.')
      } else if (data.type === 'IDMC_SEND_PROMPT' && typeof data.prompt === 'string') {
        handleSendMessage(data.prompt)
      }
    }
    window.addEventListener('message', handleMessage)

    const convEl = conversationRef.current
    const handleKeyDown = () => {
      recordActivity()
    }
    if (convEl) {
      convEl.addEventListener('keydown', handleKeyDown, { passive: true })
    }

    return () => {
      window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', handleVisibility)
      window.removeEventListener('focus', handleVisibility)
      window.removeEventListener('message', handleMessage)
      if (convEl) {
        convEl.removeEventListener('keydown', handleKeyDown)
      }
    }
  }, [appendMessage, getInactivityInsightMs, getNextInsight, getSessionTimeoutMs, handleSendMessage, isAssistantLoading, recordActivity])

  const latest = useRef({ messages, isAssistantLoading })
  useEffect(() => {
    latest.current = { messages, isAssistantLoading }
  }, [messages, isAssistantLoading])
  useEffect(
    () => () => {
      if (latest.current.isAssistantLoading) {
        onSave({
          id: conversation.id,
          updatedAt: Date.now(),
          messages: [
            ...latest.current.messages,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              status: 'error',
              text: 'Jawaban dihentikan saat berpindah percakapan. Kirim ulang pertanyaan untuk mencoba lagi.',
            },
          ],
        })
      }
    },
    [conversation.id, onSave],
  )
  useEffect(() => {
    if (messages.length)
      onSave({ id: conversation.id, messages, updatedAt: Date.now() })
  }, [messages, conversation.id, onSave])
  const hasMessages = messages.length > 0
  return (
    <div
      ref={conversationRef}
      className={`web-conversation ${hasMessages ? 'web-conversation-active' : 'web-conversation-home'}`}
    >
      {hasMessages ? (
        <MessageList
          messages={messages}
          isAssistantLoading={isAssistantLoading}
          onSendPrompt={handleSendMessage}
        />
      ) : (
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
      )}
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
            variant={hasMessages ? 'chat' : 'home'}
            placeholder="Tanyakan sesuatu tentang data DIY..."
            onSubmit={handleSendMessage}
            submitDisabled={isAssistantLoading}
            autoFocus
          />
        )}
        {!hasMessages && !isSessionExpired && (
          <SuggestionList items={suggestions} onSelect={handleSendMessage} />
        )}
        {hasMessages && !isSessionExpired && (
          <p className="web-composer-note">
            Periksa kembali jawaban dengan sumber data terkait.
          </p>
        )}
      </div>
    </div>
  )
}

function ChatWorkspace() {
  const [initial] = useState(initialConversation)
  const [active, setActive] = useState(initial.conversation)
  const [showPrivacyModal, setShowPrivacyModal] = useState(false)
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
              } as any)
            } else if ((existing as any).title !== s.title && s.title) {
              (existing as any).title = s.title
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
            } as any
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
        setActive(conversation)
      }
    }
    setOpenMobile(false)
  }

  const remove = (conversation: SavedConversation) => {
    try {
      localStorage.removeItem(CONVERSATION_PREFIX + conversation.id)
    } catch {
      setNotice('Riwayat gagal dihapus dari penyimpanan browser.')
      return
    }
    deletedIds.current.add(conversation.id)
    setRecords((previous) =>
      previous.filter((item) => item.id !== conversation.id),
    )
    deleteSession(conversation.id).catch(() => {})
    if (active.id === conversation.id) select(newConversation())
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
            onClick={() => select(newConversation())}
          >
            <Plus size={18} />
            Chat baru
          </button>
        </SidebarHeader>
        <SidebarContent>
          <h2 className="web-history-label">Riwayat percakapan</h2>
          {records.length === 0 && (
            <p className="web-empty-history">
              Percakapanmu akan muncul di sini.
            </p>
          )}
          <SidebarMenu>
            {records.map((record) => (
              <SidebarMenuItem key={record.id}>
                <SidebarMenuButton
                  isActive={active.id === record.id}
                  onClick={() => select(record)}
                  title={conversationTitle(record)}
                >
                  <MessageSquare size={16} />
                  <span>{conversationTitle(record)}</span>
                </SidebarMenuButton>
                <button
                  type="button"
                  className="web-delete-chat"
                  aria-label={`Hapus percakapan ${conversationTitle(record)}`}
                  onClick={() => remove(record)}
                >
                  <Trash2 size={15} />
                </button>
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
          onSave={save}
          onResetSession={() => select(newConversation())}
          onOpenPrivacy={() => setShowPrivacyModal(true)}
        />
      </main>
      <PrivacyModal
        open={showPrivacyModal}
        onClose={() => setShowPrivacyModal(false)}
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
