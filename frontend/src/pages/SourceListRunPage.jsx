import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'

/**
 * Parse source list output into topic sections.
 * Splits on "### Topic N: Title" headers (Grok output format).
 * Falls back to splitting on numbered items ("1. **Title**").
 * Returns array of { title, body } objects.
 */
function parseTopics(text) {
  if (!text) return []

  // Try splitting on ### Topic headers first (Grok's default format)
  const topicHeaderPattern = /\n(?=###\s+Topic\s+\d+)/
  if (/###\s+Topic\s+\d+/.test(text)) {
    const parts = text.split(topicHeaderPattern)
    const topics = []
    for (const part of parts) {
      const trimmed = part.trim()
      if (!trimmed) continue
      const match = trimmed.match(/^###\s+Topic\s+(\d+):\s*(.+?)\s*\n([\s\S]*)$/)
      if (match) {
        const title = `Topic ${match[1]}: ${match[2]}`
        // Strip leading --- separators from body
        const body = match[3].replace(/^---\s*\n?/, '').trim()
        topics.push({ title, body })
      }
    }
    if (topics.length > 0) return topics
  }

  // Fallback: split on numbered items (e.g. "1. **Title**")
  const parts = text.split(/\n(?=\d+\.\s)/)
  const topics = []
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue
    const match = trimmed.match(/^(\d+)\.\s+\*{0,2}(.+?)\*{0,2}\s*\n?([\s\S]*)$/)
    if (match) {
      const title = match[2].replace(/^\*+|\*+$/g, '').trim()
      topics.push({ title: `${match[1]}. ${title}`, body: trimmed })
    }
  }
  return topics
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

  const topics = parseTopics(output)

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
          <h2>Results</h2>
          <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
            Choose a topic and click "Run Pipeline" to proceed.
          </p>

          {topics.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {topics.map((topic, i) => (
                <div
                  key={i}
                  style={{
                    padding: '1rem',
                    borderRadius: '6px',
                    border: '1px solid #ddd',
                    background: '#f9f9f9',
                  }}
                >
                  <strong style={{ fontSize: '1.1rem' }}>{topic.title}</strong>
                  <pre style={{ whiteSpace: 'pre-wrap', margin: '0.75rem 0', fontSize: '0.85rem', color: '#444' }}>
                    {topic.body}
                  </pre>
                  <button
                    onClick={() => handleRunPipeline(topic.body)}
                    style={{
                      padding: '0.5rem 1.5rem',
                      fontSize: '0.95rem',
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
