import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'

/**
 * Parse source list output into selectable topic sections.
 * Splits on numbered topics (e.g. "1. **Title**" or "1. Title").
 * Returns array of { title, body } objects.
 */
function parseTopics(text) {
  if (!text) return []

  // Split on lines that start with a digit followed by ". " (numbered topics)
  const parts = text.split(/\n(?=\d+\.\s)/)

  const topics = []
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue

    // Check if this part starts with a numbered topic
    const match = trimmed.match(/^(\d+)\.\s+\*{0,2}(.+?)\*{0,2}\s*\n?([\s\S]*)$/)
    if (match) {
      // Clean up the title — remove leading/trailing ** markdown bold
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
  const [selectedTopic, setSelectedTopic] = useState(null)
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
    setSelectedTopic(null)
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

  function handleProceed() {
    if (!selectedTopic) return
    navigate(`/pipeline?story_id=${storyId}&selected=${encodeURIComponent(selectedTopic.substring(0, 2000))}`)
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
            Click a topic to select it, then click "Proceed to Pipeline".
          </p>

          {topics.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {topics.map((topic, i) => (
                <div
                  key={i}
                  onClick={() => setSelectedTopic(topic.body)}
                  style={{
                    padding: '1rem',
                    borderRadius: '6px',
                    border: selectedTopic === topic.body ? '2px solid #007bff' : '1px solid #ddd',
                    background: selectedTopic === topic.body ? '#e7f1ff' : '#f9f9f9',
                    cursor: 'pointer',
                  }}
                >
                  <strong style={{ fontSize: '1.05rem' }}>{topic.title}</strong>
                  <pre style={{ whiteSpace: 'pre-wrap', margin: '0.5rem 0 0', fontSize: '0.85rem', color: '#444' }}>
                    {topic.body.replace(/^\d+\.\s+\*{0,2}.+?\*{0,2}\s*\n?/, '').trim()}
                  </pre>
                </div>
              ))}
            </div>
          ) : (
            <pre style={{ background: '#f9f9f9', padding: '1rem', borderRadius: '6px', whiteSpace: 'pre-wrap', border: '1px solid #ddd' }}>
              {output}
            </pre>
          )}

          <button
            onClick={handleProceed}
            disabled={!selectedTopic}
            style={{
              marginTop: '1rem',
              padding: '0.75rem 2rem',
              fontSize: '1rem',
              background: selectedTopic ? '#007bff' : '#ccc',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: selectedTopic ? 'pointer' : 'not-allowed',
            }}
          >
            {selectedTopic ? 'Proceed to Pipeline' : 'Select a topic to proceed'}
          </button>
        </div>
      )}
    </div>
  )
}

export default SourceListRunPage
