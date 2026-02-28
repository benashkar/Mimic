// Shared source list parsing utilities.
// Used by SourceListRunPage and BatchReviewPage.

// Parse Grok source list output into individual sources.
// Handles: List A/B with URLs, topic headers with numbered posts, fallback blocks.
// Returns flat array of { label, body } -- one entry per individual source.
export function parseSources(text) {
  if (!text) return []

  const items = []

  // --- Format A: **List X: ...** headers with URLs underneath ---
  if (/\*\*List\s+[A-Z]/.test(text)) {
    const sections = text.split(/\n(?=\*\*List\s+[A-Z])/)
    for (const section of sections) {
      const s = section.trim()
      if (!s) continue
      const headerMatch = s.match(/^\*\*(.+?)\*\*\s*\n?([\s\S]*)$/)
      if (!headerMatch) continue
      const groupTitle = headerMatch[1].trim()
      const body = headerMatch[2].trim()
      const lines = body.split('\n').map(l => l.trim()).filter(l => l.length > 0)
      for (const line of lines) {
        items.push({ label: `${groupTitle}: ${line.substring(0, 80)}`, body: line })
      }
    }
    if (items.length > 0) return items
  }

  // --- Format B: ### or #### topic headers with numbered posts ---
  if (/#{3,4}\s+(?:Topic\s+)?\d/.test(text)) {
    const sections = text.split(/\n(?=#{3,4}\s+(?:Topic\s+)?\d)/)
    for (const section of sections) {
      const trimmed = section.trim()
      if (!trimmed) continue
      const headerMatch = trimmed.match(/^#{3,4}\s+(?:Topic\s+)?(\d+)[.:]\s*(.+?)\s*\n([\s\S]*)$/)
      if (!headerMatch) continue
      const topicTitle = headerMatch[2].replace(/^\*+|\*+$/g, '').trim()
      const topicBody = headerMatch[3]

      const postParts = topicBody.split(/\n(?=\s*\d+\.\s+\*\*)/)
      let foundPosts = false

      for (const part of postParts) {
        const p = part.trim()
        if (!p || !/^\d+\.\s+\*\*/.test(p)) continue
        foundPosts = true

        const authorMatch = p.match(/\*\*Author\*\*:\s*(.+?)(?:\n|$)/)
        const author = authorMatch ? authorMatch[1].trim() : ''

        const contentMatch = p.match(/\*\*Post(?:\s+Content)?\*\*:\s*["\u201C\u201D]?([\s\S]*?)["\u201C\u201D]?\s*(?:\*\*Link\*\*:|\*\*Engagement\*\*:|$)/)
        const content = contentMatch ? contentMatch[1].replace(/["\u201C\u201D]/g, '').trim() : ''

        const label = author
          ? `${topicTitle} \u2014 ${author}${content ? ': ' + content.substring(0, 80) + '...' : ''}`
          : `${topicTitle} \u2014 Post`

        items.push({ label, body: p })
      }

      if (!foundPosts) {
        items.push({
          label: `${headerMatch[1]}. ${topicTitle}`,
          body: topicBody.replace(/^---\s*\n?/, '').trim(),
        })
      }
    }
    if (items.length > 0) return items
  }

  // --- Format C: Fallback — split on blank-line-separated blocks ---
  const blocks = text.split(/\n\s*\n/).map(b => b.trim()).filter(b => b.length > 0)
  if (blocks.length > 1) {
    for (const block of blocks) {
      const hasUrl = /https?:\/\//.test(block)
      const hasHandle = /@\w+/.test(block)
      const hasTweetIndicator = /\b(Author|Tweet|Content|Post \d):/i.test(block)

      if (!hasUrl && !hasHandle && !hasTweetIndicator) continue

      const lower = block.toLowerCase()
      if (/^\*\*search parameters\*\*/i.test(block)) continue
      if (/^\*\*context\*\*/i.test(block)) continue
      if (/^\*\*localization note\*\*/i.test(block)) continue
      if (/^#{1,4}\s+.*search results/i.test(block)) continue

      items.push({ label: block.substring(0, 100) + (block.length > 100 ? '...' : ''), body: block })
    }
  }

  return items
}

// Find enrichment data for a source body by matching URLs in the body text.
export function findEnrichment(body, enrichments) {
  if (!enrichments || !body) return null
  const urlMatch = body.match(/https?:\/\/[^\s<>"']+/)
  if (!urlMatch) return null
  const url = urlMatch[0].replace(/[.,;:!?)>\]})]+$/, '')
  return enrichments[url] || null
}

// Render text with URLs converted to clickable links.
export function LinkifiedText({ text }) {
  if (!text) return null
  const parts = text.split(/(https?:\/\/[^\s<>"']+)/g)
  return parts.map((part, i) => {
    if (/^https?:\/\//.test(part)) {
      const clean = part.replace(/[.,;:!?)>\]})]+$/, '')
      const trailing = part.slice(clean.length)
      return (
        <span key={i}>
          <a href={clean} target="_blank" rel="noopener noreferrer" style={{ color: '#1da1f2' }}>{clean}</a>
          {trailing}
        </span>
      )
    }
    return <span key={i}>{part}</span>
  })
}
