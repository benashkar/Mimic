import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'

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

  function handleProceed() {
    const selectedText = window.getSelection().toString() || output
    navigate(`/pipeline?story_id=${storyId}&selected=${encodeURIComponent(selectedText.substring(0, 2000))}`)
  }

  if (!promptId) {
    return <p>No prompt_id provided. Go to <a href="/prompts">Prompt Library</a> and run a Source List.</p>
  }

  return (
    <div>
      <h1>Source List Runner</h1>

      {prompt && (
        <div style={{ background: '#f4f4f4', padding: '1rem', borderRadius: '6px', marginBottom: '1rem' }}>
          <h3>{prompt.name}</h3>
          {prompt.opportunity && <p><strong>Opportunity:</strong> {prompt.opportunity} | <strong>State:</strong> {prompt.state}</p>}
          {prompt.publications && <p><strong>Publications:</strong> {prompt.publications}</p>}
          {prompt.pitches_per_week && <p><strong>Pitches/Week:</strong> {prompt.pitches_per_week}</p>}
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
          <p style={{ color: '#666', fontSize: '0.9rem' }}>Select text below to choose a story, then click "Proceed to Pipeline".</p>
          <pre style={{ background: '#f9f9f9', padding: '1rem', borderRadius: '6px', whiteSpace: 'pre-wrap', border: '1px solid #ddd' }}>
            {output}
          </pre>
          <button onClick={handleProceed} style={{ marginTop: '1rem', padding: '0.75rem 2rem', fontSize: '1rem', background: '#007bff', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            Proceed to Pipeline
          </button>
        </div>
      )}
    </div>
  )
}

export default SourceListRunPage
