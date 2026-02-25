import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'

/**
 * Parse Grok source list output into individual sources.
 *
 * Handles multiple Grok output formats:
 *   A) **List A/B** headers with URLs on separate lines
 *   B) ### / #### topic headers with numbered posts containing **Author**/**Post**
 *   C) Fallback: split on any line that looks like a standalone URL or numbered item
 *
 * Returns flat array of { label, body } — one entry per individual source.
 */
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
        const contentMatch = p.match(/\*\*Post(?:\s+Content)?\*\*:\s*["""]?([\s\S]*?)["""]?\s*(?:\*\*Link\*\*:|\*\*Engagement\*\*:|$)/)
        const content = contentMatch ? contentMatch[1].replace(/["""]/g, '').trim() : ''

        const label = author
          ? `${topicTitle} — ${author}${content ? ': ' + content.substring(0, 80) + '...' : ''}`
          : `${topicTitle} — Post`

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
  // Only use fallback if we get multiple blocks
  if (blocks.length > 1) {
    for (const block of blocks) {
      // Skip preamble/methodology blocks (long paragraphs without links or bold)
      if (block.length > 500 && !block.includes('http') && !/\*\*/.test(block)) continue
      items.push({ label: block.substring(0, 100) + (block.length > 100 ? '...' : ''), body: block })
    }
  }

  return items
}

function SourceListRunPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const promptId = searchParams.get('prompt_id')

  const [prompt, setPrompt] = useState(null)
  const [output, setOutput] = useState(null)
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
              {sources.map((source, i) => (
                <div
                  key={i}
                  style={{
                    padding: '1rem',
                    borderRadius: '6px',
                    border: '1px solid #ddd',
                    background: '#f9f9f9',
                  }}
                >
                  <div style={{ fontWeight: 'bold', fontSize: '0.95rem', marginBottom: '0.5rem', color: '#333' }}>
                    {i + 1}. {source.label}
                  </div>
                  <pre style={{ whiteSpace: 'pre-wrap', margin: '0.5rem 0', fontSize: '0.8rem', color: '#555', maxHeight: '150px', overflow: 'auto' }}>
                    {source.body}
                  </pre>
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
              ))}
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
