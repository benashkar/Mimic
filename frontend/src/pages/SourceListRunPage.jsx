import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'

// Parse Grok source list output into individual sources.
// Handles: List A/B with URLs, topic headers with numbered posts, fallback blocks.
// Returns flat array of { label, body } -- one entry per individual source.
function parseSources(text) {
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
      // Each non-empty line is a separate source
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

      // Split into individual numbered posts (handles indentation)
      const postParts = topicBody.split(/\n(?=\s*\d+\.\s+\*\*)/)
      let foundPosts = false

      for (const part of postParts) {
        const p = part.trim()
        if (!p || !/^\d+\.\s+\*\*/.test(p)) continue
        foundPosts = true

        // Extract author for the label
        const authorMatch = p.match(/\*\*Author\*\*:\s*(.+?)(?:\n|$)/)
        const author = authorMatch ? authorMatch[1].trim() : ''

        // Extract post content for the label
        const contentMatch = p.match(/\*\*Post(?:\s+Content)?\*\*:\s*["\u201C\u201D]?([\s\S]*?)["\u201C\u201D]?\s*(?:\*\*Link\*\*:|\*\*Engagement\*\*:|$)/)
        const content = contentMatch ? contentMatch[1].replace(/["\u201C\u201D]/g, '').trim() : ''

        const label = author
          ? `${topicTitle} \u2014 ${author}${content ? ': ' + content.substring(0, 80) + '...' : ''}`
          : `${topicTitle} \u2014 Post`

        items.push({ label, body: p })
      }

      // If no numbered posts found in this topic, add the whole topic as one item
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
      // Only include blocks that look like actual source content:
      // must contain a URL, @handle, or tweet/author indicators
      const hasUrl = /https?:\/\//.test(block)
      const hasHandle = /@\w+/.test(block)
      const hasTweetIndicator = /\b(Author|Tweet|Content|Post \d):/i.test(block)

      if (!hasUrl && !hasHandle && !hasTweetIndicator) continue

      // Still skip metadata blocks that mention search methodology
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
function findEnrichment(body, enrichments) {
  if (!enrichments || !body) return null
  const urlMatch = body.match(/https?:\/\/[^\s<>"']+/)
  if (!urlMatch) return null
  const url = urlMatch[0].replace(/[.,;:!?)>\]})]+$/, '')
  return enrichments[url] || null
}

// Render text with URLs converted to clickable links.
function LinkifiedText({ text }) {
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

function SourceListRunPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const promptId = searchParams.get('prompt_id')

  const [prompt, setPrompt] = useState(null)
  const [output, setOutput] = useState(null)
  const [enrichments, setEnrichments] = useState(null)
  const [storyId, setStoryId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [statusMsg, setStatusMsg] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (promptId) {
      apiClient(`/prompts/${promptId}`)
        .then(setPrompt)
        .catch((err) => setError(err.message))
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [promptId])

  async function handleRun() {
    setLoading(true)
    setError(null)
    setStatusMsg('Sending request...')
    try {
      const data = await apiClient('/pipeline/source-list', {
        method: 'POST',
        body: JSON.stringify({ prompt_id: parseInt(promptId, 10) }),
      })

      if (!data || !data.story_id) {
        throw new Error('Server did not return a story_id')
      }

      setStoryId(data.story_id)
      setStatusMsg('Waiting for Grok API response (this may take up to 60 seconds)...')

      // Start polling
      pollRef.current = setInterval(async () => {
        try {
          const status = await apiClient(`/pipeline/status/${data.story_id}`)
          if (status.status === 'completed') {
            clearInterval(pollRef.current)
            setOutput(status.source_list_output)
            if (status.url_enrichments) {
              try {
                setEnrichments(JSON.parse(status.url_enrichments))
              } catch (_) { /* ignore parse errors */ }
            }
            setStatusMsg(null)
            setLoading(false)
          } else if (status.status === 'failed') {
            clearInterval(pollRef.current)
            const failedRun = status.runs.find(r => r.status === 'failed')
            setError(failedRun ? failedRun.error_message : 'Pipeline failed')
            setStatusMsg(null)
            setLoading(false)
          }
        } catch (err) {
          clearInterval(pollRef.current)
          setError(err.message)
          setStatusMsg(null)
          setLoading(false)
        }
      }, 2000)
    } catch (err) {
      setError(err.message)
      setStatusMsg(null)
      setLoading(false)
    }
  }

  function handleRunPipeline(topicBody) {
    navigate(`/pipeline?story_id=${storyId}&selected=${encodeURIComponent(topicBody.substring(0, 2000))}`)
  }

  if (!promptId) {
    return <p>No prompt_id provided. Go to <a href="/prompts">Prompt Library</a> and run a Source List.</p>
  }

  const sources = parseSources(output)

  return (
    <div>
      <h1>Source List Runner</h1>

      {prompt && (
        <div style={{ background: '#f4f4f4', padding: '1rem', borderRadius: '6px', marginBottom: '1rem' }}>
          <h3>{prompt.name}</h3>
          {prompt.opportunity && <p><strong>Opportunity:</strong> {prompt.opportunity} | <strong>State:</strong> {prompt.state}</p>}
          {prompt.publications && <p><strong>Publications:</strong> {prompt.publications}</p>}
          {prompt.pitches_per_week && <p><strong>Pitches/Week:</strong> {prompt.pitches_per_week}</p>}
          <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#fff', borderRadius: '4px', border: '1px solid #ddd' }}>
            <strong>Prompt Text:</strong>
            <p style={{ whiteSpace: 'pre-wrap', margin: '0.5rem 0 0', fontSize: '0.9rem', color: '#333' }}>{prompt.prompt_text}</p>
          </div>
        </div>
      )}

      {!output && (
        <div>
          <button onClick={handleRun} disabled={loading} style={{ padding: '0.75rem 2rem', fontSize: '1rem' }}>
            {loading ? 'Running...' : 'Run Source List'}
          </button>
          {statusMsg && <p style={{ color: '#007bff', marginTop: '0.5rem' }}>{statusMsg}</p>}
        </div>
      )}

      {error && <p style={{ color: 'red', marginTop: '1rem' }}>Error: {error}</p>}

      {output && (
        <div style={{ marginTop: '1rem' }}>
          <h2>{sources.length} Sources Found</h2>
          <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
            Each source below can be sent to the pipeline individually.
          </p>

          {sources.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {sources.map((source, i) => {
                const enrichment = findEnrichment(source.body, enrichments)
                return (
                  <div
                    key={i}
                    style={{
                      padding: '1rem',
                      borderRadius: '6px',
                      border: '1px solid #ddd',
                      background: enrichment?.type === 'twitter'
                        ? '#e8f4fd'
                        : enrichment?.type === 'website'
                          ? '#e8f5e9'
                          : '#f9f9f9',
                    }}
                  >
                    <div style={{ fontWeight: 'bold', fontSize: '0.95rem', marginBottom: '0.5rem', color: '#333' }}>
                      {i + 1}. {source.label}
                    </div>

                    {enrichment?.type === 'twitter' && (
                      <div style={{ margin: '0.5rem 0', padding: '0.75rem', background: '#fff', borderRadius: '4px', border: '1px solid #b3d9f2' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                          <span style={{ fontWeight: 'bold', color: '#1da1f2' }}>
                            @{enrichment.author_name}
                          </span>
                          {enrichment.created_at && (
                            <span style={{ fontSize: '0.8rem', color: '#888' }}>
                              {new Date(enrichment.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                            </span>
                          )}
                        </div>
                        <p style={{ margin: '0 0 0.5rem', fontSize: '0.9rem', color: '#333' }}>
                          {enrichment.text}
                        </p>
                        <a
                          href={enrichment.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: '#1da1f2', fontSize: '0.85rem' }}
                        >
                          {enrichment.url}
                        </a>
                      </div>
                    )}

                    {enrichment?.type === 'website' && (
                      <div style={{ margin: '0.5rem 0', padding: '0.75rem', background: '#fff', borderRadius: '4px', border: '1px solid #a5d6a7' }}>
                        {enrichment.title && (
                          <div style={{ fontWeight: 'bold', marginBottom: '0.25rem', color: '#2e7d32' }}>
                            {enrichment.title}
                          </div>
                        )}
                        <p style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: '#555' }}>
                          {enrichment.text}
                        </p>
                        <a
                          href={enrichment.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: '#2e7d32', fontSize: '0.85rem' }}
                        >
                          {enrichment.url}
                        </a>
                      </div>
                    )}

                    {!enrichment && (
                      <pre style={{ whiteSpace: 'pre-wrap', margin: '0.5rem 0', fontSize: '0.8rem', color: '#555', maxHeight: '150px', overflow: 'auto' }}>
                        <LinkifiedText text={source.body} />
                      </pre>
                    )}

                    <button
                      onClick={() => handleRunPipeline(source.body)}
                      style={{
                        padding: '0.4rem 1.25rem',
                        fontSize: '0.9rem',
                        background: '#007bff',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                      }}
                    >
                      Run Pipeline
                    </button>
                  </div>
                )
              })}
            </div>
          ) : (
            <pre style={{ background: '#f9f9f9', padding: '1rem', borderRadius: '6px', whiteSpace: 'pre-wrap', border: '1px solid #ddd' }}>
              {output}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

export default SourceListRunPage
