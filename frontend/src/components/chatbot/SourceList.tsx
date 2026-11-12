import { cn } from '../../lib/utils'
import type { ChatSource } from './types'

export interface SourceListProps {
  sources: ChatSource[]
}

function formatDate(value?: string): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('id-ID', { dateStyle: 'medium' }).format(date)
}

function sourceDetails(source: ChatSource): string {
  const parts: string[] = []
  if (source.rowsCovered) {
    parts.push(`Baris ${source.rowsCovered.replace(' of ', ' dari ')}`)
  }
  const dataAsOf = formatDate(source.dataAsOf)
  if (dataAsOf) parts.push(`Data ${dataAsOf}`)
  if (source.possiblyOutdated) parts.push('mungkin basi')
  return parts.join(' · ')
}

/** Compact, non-interactive citation cards under an assistant reply. */
export function SourceList({ sources }: SourceListProps) {
  if (sources.length === 0) return null

  return (
    <div
      className={cn(
        'idmc-sources',
        '[margin-block-start:var(--idmc-space-3)]',
        '[border-block-start:var(--idmc-stroke-1)_solid_var(--idmc-color-neutral-300)]',
        '[padding-block-start:var(--idmc-space-2)]',
      )}
    >
      <p
        className={cn(
          '[margin:0_0_var(--idmc-space-1)] [color:var(--idmc-color-neutral-600)]',
          '[font:var(--idmc-type-b4)] [font-weight:600] [letter-spacing:0]',
        )}
      >
        Sumber
      </p>
      <ul
        className={cn(
          'flex flex-col [gap:var(--idmc-space-1)] [margin:0] [padding:0] list-none',
        )}
      >
        {sources.map((source, index) => {
          const details = sourceDetails(source)
          return (
            <li
              key={`${source.dashboard ?? ''}-${source.chart ?? ''}-${String(source.sliceId ?? '')}-${index}`}
              className={cn(
                '[padding:var(--idmc-space-1)_var(--idmc-space-2)]',
                '[border-radius:var(--idmc-radius-2)] [background:var(--idmc-color-neutral-100)]',
                '[font:var(--idmc-type-b4)] [letter-spacing:0]',
              )}
            >
              <p className="[margin:0] [color:var(--idmc-color-neutral-900)] [font-weight:600]">
                {source.dashboard ?? 'Dashboard'} — {source.chart ?? 'Chart'}
              </p>
              {details && (
                <p className="[margin:0] [color:var(--idmc-color-neutral-600)]">{details}</p>
              )}
              {source.sourceUrl && (
                <a
                  href={source.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(
                    'inline-flex items-center gap-1 [margin-block-start:var(--idmc-space-1)]',
                    '[font:var(--idmc-type-b4)] [color:var(--idmc-color-primary-600)] hover:[color:var(--idmc-color-primary-700)]',
                    'underline [font-weight:600]',
                  )}
                >
                  <span>🔗 Buka di Portal IDMC</span>
                  <span aria-hidden="true">↗</span>
                </a>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
