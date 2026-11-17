import { widgetClasses } from './layout'
import { cn } from '../../lib/utils'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { AnimationEvent } from 'react'
import { listSessions } from '../../api/sessionsApi'
import { ChatLauncher } from './ChatLauncher'
import { ConversationView } from './ConversationView'
import { HistoryView } from './HistoryView'
import { HomeView } from './HomeView'
import type { ChatHistoryItem, ChatUser } from './types'
import { useChatSession } from './useChatSession'
import type { ChatTransport } from '../../api/chatTransport'
import { DYNAMIC_INSIGHTS_POOL, formatInsightMessage } from './insights'
import type { DynamicInsight } from './insights'
import { getLocalSessionSummaries, clearLocalSessions } from './localHistory'

type ChatView = 'home' | 'chat' | 'history'

/** `closing` keeps the panel mounted just long enough to play its exit animation. */
type OverlayPhase = 'closed' | 'open' | 'closing'

/** Safety net in case the exit animation never reports its end (hidden tab, interrupted). */
const CLOSE_FALLBACK_MS = 300

/**
 * Dynamic insight engagement threshold: 2 minutes (120,000 ms).
 * Standard HCI / web assistant proactive nudge period.
 */
export const INACTIVITY_INSIGHT_MS = 120_000

/**
 * Session timeout threshold: 5 minutes (300,000 ms).
 * Industry benchmark matching AWS Lex default TTL (300s) and OWASP 2-5m idle guidelines.
 */
export const SESSION_TIMEOUT_MS = 300_000

/** Backwards-compatibility alias for tests referencing IDLE_TIMEOUT_MS */
export const IDLE_TIMEOUT_MS = INACTIVITY_INSIGHT_MS

/** Backwards-compatibility alias for tests referencing IDLE_NUDGE_MESSAGE */
export const IDLE_NUDGE_MESSAGE = formatInsightMessage(DYNAMIC_INSIGHTS_POOL[0]!)

export const SESSION_EXPIRED_MESSAGE =
  '**Sesi Telah Berakhir**\n\n' +
  'Sesi percakapan ditutup otomatis karena tidak ada aktivitas selama 5 menit. ' +
  'Riwayat percakapan di atas tetap dapat Anda baca. Silakan klik tombol **Mulai Sesi Baru** di bawah untuk memulai percakapan baru.'

const HISTORY_ERROR =
  'Riwayat chat tidak bisa dimuat. Periksa koneksi backend lalu coba lagi.'
const OPEN_SESSION_ERROR = 'Percakapan tidak bisa dibuka. Coba lagi.'

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

export interface ChatOverlayProps {
  user: ChatUser
  suggestions: string[]
  /**
   * Optional mock list for the History view. When omitted, the overlay loads
   * real sessions from `/api/sessions` with local storage fallback.
   */
  historyItems?: ChatHistoryItem[]
  /** Preview defaults to the Vite API proxy; the extension injects its transport. */
  requestReply?: ChatTransport
  /** Preview defaults to true; the extension passes true. */
  historyEnabled?: boolean
}

/**
 * Floating chatbot. One bottom-right anchor is shared by both states: while
 * closed only the launcher is rendered, while open only the panel is.
 * Features 2-minute dynamic insight rotation and 5-minute graceful session expiry
 * powered by a reliable wall-clock heartbeat engine.
 */
export function ChatOverlay({
  user,
  suggestions,
  historyItems: historyItemsProp,
  requestReply,
  historyEnabled = true,
}: ChatOverlayProps) {
  const [phase, setPhase] = useState<OverlayPhase>('closed')
  const [view, setView] = useState<ChatView>('home')
  const [isSessionExpired, setIsSessionExpired] = useState(false)
  const {
    messages,
    isAssistantLoading,
    isHydrating,
    sendMessage,
    loadSession,
    resetConversation,
    appendMessage,
  } = useChatSession(requestReply)
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null)
  const [historyItems, setHistoryItems] = useState<ChatHistoryItem[]>(historyItemsProp ?? [])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)

  const panelRef = useRef<HTMLDivElement>(null)
  const launcherRef = useRef<HTMLButtonElement>(null)
  const wasActiveRef = useRef(false)
  const shownInsightIdsRef = useRef<string[]>([])

  // Wall-clock tracking refs (immune to timer drift and mousemove jitter)
  const lastActivityTimeRef = useRef<number>(Date.now())
  const lastInsightTimeRef = useRef<number>(0)
  const isSessionExpiredRef = useRef<boolean>(false)

  // Keep isSessionExpiredRef in sync
  useEffect(() => {
    isSessionExpiredRef.current = isSessionExpired
  }, [isSessionExpired])

  // The view History was opened from, so Back returns to it. Written only when History opens.
  const previousViewRef = useRef<Exclude<ChatView, 'history'>>('home')

  const recordActivity = useCallback(() => {
    if (isSessionExpiredRef.current) return
    lastActivityTimeRef.current = Date.now()
    lastInsightTimeRef.current = 0
  }, [])

  // Final step of closing: unmount the panel and preserve conversation state.
  const finishClose = useCallback(() => {
    setPhase('closed')
    setSelectedHistoryId(null)
    setHistoryError(null)
  }, [])

  // Start closing: play the exit animation first, or skip it for reduced motion.
  const requestClose = useCallback(() => {
    if (prefersReducedMotion()) finishClose()
    else setPhase((current) => (current === 'open' ? 'closing' : current))
  }, [finishClose])

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

  const customInsightMsRef = useRef<number | null>(null)
  const customTimeoutMsRef = useRef<number | null>(null)

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

  // Inactivity Heartbeat: checks wall-clock time every 1,000ms
  useEffect(() => {
    if (phase !== 'open') return

    // Initialize activity on open
    lastActivityTimeRef.current = Date.now()
    lastInsightTimeRef.current = 0

    console.info(
      `[IDMC Chatbot] Mesin Idle Aktif: Tier 1 Insight = ${Math.floor(getInactivityInsightMs() / 1000)}s, Tier 2 Timeout = ${Math.floor(getSessionTimeoutMs() / 1000)}s.\n` +
      `Panduan Pengujian Cepat di Console:\n` +
      `  - Uji Wawasan Instan: window.postMessage({ type: 'IDMC_TRIGGER_INSIGHT' }, '*')\n` +
      `  - Uji Selesai Sesi Instan: window.postMessage({ type: 'IDMC_TRIGGER_TIMEOUT' }, '*')\n` +
      `  - Mode Cepat (10s/25s): window.postMessage({ type: 'IDMC_SET_FAST_TIMERS' }, '*')`,
    )

    let lastLoggedSecond = 0

    const checkInactivity = () => {
      if (isSessionExpiredRef.current || isAssistantLoading || isHydrating) {
        return
      }

      const now = Date.now()
      const idleMs = now - lastActivityTimeRef.current
      const insightMs = getInactivityInsightMs()
      const timeoutMs = getSessionTimeoutMs()
      const idleSec = Math.floor(idleMs / 1000)

      // Periodic observable log every 30s
      if (idleSec > 0 && idleSec % 30 === 0 && idleSec !== lastLoggedSecond) {
        lastLoggedSecond = idleSec
        console.log(`[IDMC Chatbot] Waktu idle: ${idleSec}s (Target Insight: ${Math.floor(insightMs / 1000)}s | Target Timeout: ${Math.floor(timeoutMs / 1000)}s)`)
      }

      // Tier 2: 5 minutes idle -> Graceful Session Expiration
      if (idleMs >= timeoutMs) {
        isSessionExpiredRef.current = true
        setIsSessionExpired(true)
        appendMessage('assistant', SESSION_EXPIRED_MESSAGE)
        setView((current) => (current === 'home' ? 'chat' : current))
        console.warn(`[IDMC Chatbot] Tier 2 Trigger: Sesi ditutup otomatis setelah ${idleSec}s tidak aktif (AWS Lex/OWASP benchmark).`)
        return
      }

      // Tier 1: 2 minutes idle -> Proactive Dynamic Rotating Insight
      if (idleMs >= insightMs) {
        const msSinceLastInsight = now - lastInsightTimeRef.current
        if (lastInsightTimeRef.current === 0 || msSinceLastInsight >= insightMs) {
          lastInsightTimeRef.current = now
          const insight = getNextInsight()
          appendMessage('assistant', formatInsightMessage(insight))
          setView((current) => (current === 'home' ? 'chat' : current))
          console.info(`[IDMC Chatbot] Tier 1 Trigger: Wawasan dataset ditampilkan (${idleSec}s idle): "${insight.title}"`)
        }
      }
    }

    const intervalId = window.setInterval(checkInactivity, 1_000)

    // Check immediately when tab becomes visible or receives focus (recovers from tab throttling)
    const handleVisibility = () => {
      if (!document.hidden) {
        checkInactivity()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    window.addEventListener('focus', handleVisibility)

    // Bridge for instant QA testing and prompt hyperlinks from any context
    const handleMessage = (event: MessageEvent) => {
      const data = event.data
      if (!data || typeof data !== 'object') return

      if (data.type === 'IDMC_TRIGGER_INSIGHT') {
        const insight = getNextInsight()
        appendMessage('assistant', formatInsightMessage(insight))
        setView((current) => (current === 'home' ? 'chat' : current))
        console.info('[IDMC Chatbot] Manual Trigger: Wawasan dataset berhasil dimunculkan.')
      } else if (data.type === 'IDMC_TRIGGER_TIMEOUT') {
        isSessionExpiredRef.current = true
        setIsSessionExpired(true)
        appendMessage('assistant', SESSION_EXPIRED_MESSAGE)
        setView((current) => (current === 'home' ? 'chat' : current))
        console.warn('[IDMC Chatbot] Manual Trigger: Sesi expired berhasil dimunculkan.')
      } else if (data.type === 'IDMC_SET_FAST_TIMERS') {
        customInsightMsRef.current = 10_000
        customTimeoutMsRef.current = 25_000
        console.info('[IDMC Chatbot] Mode Cepat Aktif: Insight 10 detik, Timeout 25 detik.')
      } else if (data.type === 'IDMC_RESET_TIMERS') {
        customInsightMsRef.current = null
        customTimeoutMsRef.current = null
        console.info('[IDMC Chatbot] Timers kembali ke standar: Insight 120 detik, Timeout 300 detik.')
      } else if (data.type === 'IDMC_SEND_PROMPT' && typeof data.prompt === 'string') {
        recordActivity()
        setIsSessionExpired(false)
        void sendMessage(data.prompt)
        setView('chat')
      }
    }
    window.addEventListener('message', handleMessage)

    // User activity listener: keydown inside the panel (typing) resets idle timer
    const panel = panelRef.current
    const handleKeyDown = () => {
      recordActivity()
    }

    if (panel) {
      panel.addEventListener('keydown', handleKeyDown, { passive: true })
    }

    return () => {
      window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', handleVisibility)
      window.removeEventListener('focus', handleVisibility)
      window.removeEventListener('message', handleMessage)
      if (panel) {
        panel.removeEventListener('keydown', handleKeyDown)
      }
    }
  }, [phase, isAssistantLoading, isHydrating, recordActivity, getNextInsight, appendMessage, getInactivityInsightMs, getSessionTimeoutMs])

  // Home submit or suggestion click: send the text and switch to Conversation.
  const startConversation = (text: string) => {
    recordActivity()
    setIsSessionExpired(false)
    void sendMessage(text)
    setView('chat')
  }

  const handleSendMessage = (text: string) => {
    recordActivity()
    setIsSessionExpired(false)
    void sendMessage(text)
  }

  const handleStartFreshSession = useCallback(() => {
    lastActivityTimeRef.current = Date.now()
    lastInsightTimeRef.current = 0
    isSessionExpiredRef.current = false
    setIsSessionExpired(false)
    resetConversation()
    shownInsightIdsRef.current = []
    setView('home')
  }, [resetConversation])

  const openHistory = () => {
    if (!historyEnabled) return
    if (view !== 'history') previousViewRef.current = view
    setView('history')
    if (historyItemsProp !== undefined) return

    setHistoryLoading(true)
    setHistoryError(null)
    void listSessions()
      .then((sessions) => {
        if (sessions.length > 0) {
          setHistoryItems(
            sessions.slice(0, 10).map((session) => ({
              id: session.id,
              title: session.title,
              updatedAt: session.updatedAt,
            })),
          )
        } else {
          const local = getLocalSessionSummaries()
          setHistoryItems(local.slice(0, 10))
        }
      })
      .catch(() => {
        const local = getLocalSessionSummaries()
        if (local.length > 0) {
          setHistoryItems(local.slice(0, 10))
          setHistoryError(null)
        } else {
          setHistoryError(HISTORY_ERROR)
        }
      })
      .finally(() => setHistoryLoading(false))
  }

  const closeHistory = () => setView(previousViewRef.current)

  const handleClearHistory = useCallback(() => {
    clearLocalSessions()
    setHistoryItems([])
    setSelectedHistoryId(null)
    setHistoryError(null)
  }, [])

  const handleSelectHistory = (id: string) => {
    setSelectedHistoryId(id)
    if (historyItemsProp !== undefined) return

    setHistoryError(null)
    void loadSession(id)
      .then(() => {
        recordActivity()
        setIsSessionExpired(false)
        setView('chat')
      })
      .catch(() => setHistoryError(OPEN_SESSION_ERROR))
  }

  const handlePanelAnimationEnd = (event: AnimationEvent<HTMLDivElement>) => {
    // Ignore bubbled events from children (e.g. a message's entrance animation).
    if (phase === 'closing' && event.target === event.currentTarget) finishClose()
  }

  // Fallback so the panel can never get stuck in `closing`.
  useEffect(() => {
    if (phase !== 'closing') return
    const timeout = window.setTimeout(finishClose, CLOSE_FALLBACK_MS)
    return () => window.clearTimeout(timeout)
  }, [phase, finishClose])

  // Escape closes the panel.
  useEffect(() => {
    if (phase !== 'open') return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') requestClose()
    }
    // Listen inside the shadow tree so portal shortcuts do not receive our keys.
    const root = panelRef.current?.getRootNode() ?? document
    root.addEventListener('keydown', handleKeyDown as EventListener)
    return () => root.removeEventListener('keydown', handleKeyDown as EventListener)
  }, [phase, requestClose])

  // Move focus into the panel when it opens so keyboard users land inside it.
  useEffect(() => {
    if (phase === 'open') panelRef.current?.focus()
  }, [phase])

  // Switching views unmounts the focused button (history / back); hand focus back to the
  // panel instead of dropping it on <body>. A view that autofocuses (the composer) wins.
  useEffect(() => {
    const panel = panelRef.current
    const root = panel?.getRootNode()
    const activeElement = root instanceof ShadowRoot ? root.activeElement : document.activeElement
    if (phase === 'open' && panel && !panel.contains(activeElement)) panel.focus()
  }, [view, phase])

  // After the panel has closed and the launcher is back, hand focus to the launcher.
  useEffect(() => {
    if (phase === 'closed' && wasActiveRef.current) launcherRef.current?.focus()
    wasActiveRef.current = phase !== 'closed'
  }, [phase])

  return (
    <div
      className={cn(
        'idmc-chatbot idmc-overlay',
        widgetClasses,
        '[--idmc-overlay-gutter:var(--idmc-space-5)] [--idmc-overlay-launcher-size:var(--idmc-space-10)]',
        '[--idmc-overlay-panel-width:380px] [--idmc-overlay-panel-height:600px]',
        '[--idmc-overlay-inset-inline:max(_var(--idmc-overlay-gutter),_env(safe-area-inset-left,_0px),_env(safe-area-inset-right,_0px)_)]',
        '[--idmc-overlay-inset-start:max(var(--idmc-overlay-gutter),_env(safe-area-inset-top,_0px))]',
        '[--idmc-overlay-inset-end:max(var(--idmc-overlay-gutter),_env(safe-area-inset-bottom,_0px))]',
        'tablet:[--idmc-overlay-gutter:var(--idmc-space-4)] mobile:[--idmc-overlay-gutter:var(--idmc-space-3)]',
        'mobile:[--idmc-overlay-launcher-size:var(--idmc-space-9)] mobile:[--idmc-overlay-panel-width:100%]',
        'mobile:[--idmc-overlay-panel-height:100%] short:[--idmc-overlay-gutter:var(--idmc-space-2)]',
        'short:[--idmc-overlay-launcher-size:var(--idmc-space-9)]',
      )}
    >
      {phase === 'closed' ? (
        <ChatLauncher ref={launcherRef} onOpen={() => setPhase('open')} />
      ) : (
        <div
          ref={panelRef}
          className={cn(
            'idmc-overlay__panel',
            'fixed [inset-inline-end:var(--idmc-overlay-inset-inline)]',
            '[inset-block-end:var(--idmc-overlay-inset-end)] [z-index:1000]',
            '[inline-size:min(_var(--idmc-overlay-panel-width),_calc(100%_-_2_*_var(--idmc-overlay-inset-inline))_)]',
            '[block-size:min(_var(--idmc-overlay-panel-height),_calc(100%_-_var(--idmc-overlay-inset-start)_-_var(--idmc-overlay-inset-end))_)]',
            'overflow-hidden [border-radius:var(--idmc-radius-4)] [background:var(--idmc-color-neutral-200)]',
            '[box-shadow:var(--idmc-shadow-e3)] [transform-origin:100%_100%]',
            '[animation:idmc-panel-in_var(--idmc-motion-duration-base)_var(--idmc-motion-ease-out)]',
            'supports-[block-size:_100dvh]:[block-size:min(_var(--idmc-overlay-panel-height),_calc(100dvh_-_var(--idmc-overlay-inset-start)_-_var(--idmc-overlay-inset-end))_)]',
            '[&:focus-visible]:[outline:var(--idmc-stroke-2)_solid_var(--idmc-color-primary-300)]',
            '[&:focus-visible]:[outline-offset:calc(-1_*_var(--idmc-stroke-2))]',
            "[&[data-state='closing']]:[animation:idmc-panel-out_var(--idmc-motion-duration-fast)_var(--idmc-motion-ease-out)_forwards]",
            "[&[data-state='closing']]:pointer-events-none",
          )}
          data-state={phase}
          role="dialog"
          aria-label="Chatbot Data Publik"
          tabIndex={-1}
          inert={phase === 'closing'}
          onAnimationEnd={handlePanelAnimationEnd}
        >
          {view === 'home' && (
            <HomeView
              user={user}
              suggestions={suggestions}
              onSubmit={startConversation}
              onSelectSuggestion={startConversation}
              onOpenHistory={historyEnabled ? openHistory : undefined}
              onClose={requestClose}
            />
          )}
          {view === 'chat' && (
            <ConversationView
              user={user}
              messages={messages}
              isAssistantLoading={isAssistantLoading || isHydrating}
              onSend={handleSendMessage}
              onOpenHistory={historyEnabled ? openHistory : undefined}
              onClose={requestClose}
              isSessionExpired={isSessionExpired}
              onResetSession={handleStartFreshSession}
            />
          )}
          {historyEnabled && view === 'history' && (
            <HistoryView
              items={historyItems}
              selectedId={selectedHistoryId}
              onSelect={handleSelectHistory}
              onBack={closeHistory}
              onClose={requestClose}
              isLoading={historyLoading}
              error={historyError}
              onClearHistory={handleClearHistory}
            />
          )}
        </div>
      )}
    </div>
  )
}
