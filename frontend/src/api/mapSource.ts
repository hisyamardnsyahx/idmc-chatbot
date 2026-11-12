/** Maps one backend `Source` object to the UI-safe `ChatSource` shape. */

import type { ChatSource } from './types'

interface RawSource {
  dashboard?: unknown
  chart?: unknown
  slice_id?: unknown
  rows_covered?: unknown
  data_as_of?: unknown
  possibly_outdated?: unknown
  relevance?: unknown
  content?: unknown
  source_url?: unknown
}

export function mapSource(raw: unknown): ChatSource | null {
  if (typeof raw !== 'object' || raw === null) return null
  const value = raw as RawSource
  const source: ChatSource = {
    dashboard: typeof value.dashboard === 'string' ? value.dashboard : undefined,
    chart: typeof value.chart === 'string' ? value.chart : undefined,
    sliceId:
      typeof value.slice_id === 'string' || typeof value.slice_id === 'number'
        ? value.slice_id
        : undefined,
    rowsCovered: typeof value.rows_covered === 'string' ? value.rows_covered : undefined,
    dataAsOf: typeof value.data_as_of === 'string' ? value.data_as_of : undefined,
    possiblyOutdated: Boolean(value.possibly_outdated),
    relevance: typeof value.relevance === 'number' ? value.relevance : 0,
    content: typeof value.content === 'string' ? value.content : '',
  }
  if (typeof value.source_url === 'string') {
    source.sourceUrl = value.source_url
  }
  return source
}
