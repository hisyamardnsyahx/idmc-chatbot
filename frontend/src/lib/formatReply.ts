/**
 * The backend appends a plain-text ``Sumber:`` block for non-UI clients. The
 * UI renders structured source cards instead, so drop only that block while
 * preserving any following freshness note.
 */
export function stripSourceBlock(text: string): string {
  const lines = text.split(/\r?\n/)
  const start = lines.findIndex((line) => /^#{0,4}\s*Sumber:\s*$/i.test(line.trim()))
  if (start < 0) return text

  let end = start + 1
  while (end < lines.length && /^-\s+/.test(lines[end].trim())) end += 1

  return [...lines.slice(0, start), ...lines.slice(end)]
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
