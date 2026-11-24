import { widgetClasses, viewClasses } from './layout'
import { cn } from '../../lib/utils'
import { useId } from 'react'
import { ChatHeader } from './ChatHeader'
import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'
import { HistoryItem } from './HistoryItem'
import type { ChatHistoryItem } from './types'

export interface HistoryViewProps {
  items: ChatHistoryItem[]
  /** The current conversation; drawn with the stronger background. */
  selectedId?: string | null
  onSelect?: (id: string) => void
  onBack: () => void
  onMaximize?: () => void
  maximizeDisabled?: boolean
  onClose?: () => void
  isLoading?: boolean
  error?: string | null
  /** Action to clear all stored history sessions */
  onClearHistory?: () => void
}

/** History state: a compact "Recents" list. An internal widget view, not a sidebar or route. */
export function HistoryView({
  items,
  selectedId,
  onSelect,
  onBack,
  onMaximize,
  maximizeDisabled,
  onClose,
  isLoading = false,
  error = null,
  onClearHistory,
}: HistoryViewProps) {
  const labelId = useId()

  return (
    <section
      className={cn('idmc-chatbot idmc-view idmc-history', widgetClasses, viewClasses)}
      aria-label="Riwayat chat"
      aria-busy={isLoading}
    >
      <ChatHeader
        title="Riwayat Chat"
        onBack={onBack}
        onClose={onClose}
        onMaximize={onMaximize}
        maximizeDisabled={maximizeDisabled}
      />

      {isLoading ? (
        <EmptyState message="Memuat riwayat..." />
      ) : error ? (
        <div className="[padding:var(--idmc-space-4)_var(--idmc-space-3)]">
          <ErrorState>{error}</ErrorState>
        </div>
      ) : items.length === 0 ? (
        <EmptyState message="Belum ada riwayat percakapan." />
      ) : (
        <div
          className={cn(
            'idmc-history__body',
            'flex [flex:1_1_0] flex-col [min-block-size:0] [padding-block-start:var(--idmc-content-gap)]',
          )}
        >
          <div className="flex flex-none items-center justify-between [padding:var(--idmc-space-1)_var(--idmc-space-3)]">
            <h2
              className={cn(
                'idmc-history__label',
                '[margin:0]',
                '[color:var(--idmc-color-neutral-600)] [font:var(--idmc-type-b4)] [&]:[font-weight:600]',
                '[letter-spacing:0]',
              )}
              id={labelId}
            >
              Recents ({items.length}/10)
            </h2>
            {onClearHistory && (
              <button
                type="button"
                onClick={onClearHistory}
                className="text-xs font-semibold text-[var(--idmc-color-primary-500)] hover:text-[var(--idmc-color-primary-700)] hover:underline cursor-pointer bg-transparent border-0 p-0"
                title="Hapus semua riwayat percakapan"
              >
                Hapus Riwayat
              </button>
            )}
          </div>
          <ul
            className={cn(
              'idmc-history__list',
              'flex [flex:1_1_0] flex-col [gap:var(--idmc-space-0)] [min-block-size:0] [margin:0] [padding:0]',
              'overflow-x-hidden overflow-y-auto [overscroll-behavior:contain] [scrollbar-width:thin] list-none',
            )}
            aria-labelledby={labelId}
          >
            {items.map((item) => (
              <HistoryItem
                key={item.id}
                item={item}
                selected={item.id === selectedId}
                onSelect={onSelect}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
