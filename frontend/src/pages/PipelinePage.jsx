import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '../api/client'

function PipelinePage() {
  const [searchParams] = useSearchParams()
  const storyId = searchParams.get('story_id')
  const selectedStory = decodeURIComponent(searchParams.get('selected') || '')

  const [refinementPrompts, setRefinementPrompts] = useState([])
  const [selectedPromptId, setSelectedPromptId] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiClient('/prompts?type=papa')
      .then((data) => {
        setRefinementPrompts(data)
        if (data.length > 0) setSelectedPromptId(data[0].id)
      })
      .catch((err) => setError(err.message))
  }, [])

  async function handleRun() {
    if (!selectedPromptId || !storyId || !selectedStory) return
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient('/pipeline/run', {
        method: 'POST',
        body: JSON.stringify({
          story_id: parseInt(storyId, 10),
          selected_story: selectedStory,
          refinement_prompt_id: selectedPromptId,
        }),
      })
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!storyId) {
    return <p>No story selected. Go to <a href="/prompts">Prompt Library</a> and run a Source List first.</p>
  }

  return (
    <div>
      <h1>Pipeline</h1>

      <div style={{ background: '#f4f4f4', padding: '1rem', borderRadius: '6px', marginBottom: '1rem' }}>
        <h3>Selected Story/Source</h3>
        <pre style={{ whiteSpace: 'pre-wrap', maxHeight: '200px', overflow: 'auto' }}>{selectedStory}</pre>
      </div>

      {!result && (
        <>
          <h2>Pick Refinement Type</h2>
          <p style={{ color: '#666' }}>Is this an announcement or a statement?</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
            {refinementPrompts.map((p) => (
              <label key={p.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', padding: '0.5rem', border: selectedPromptId === p.id ? '2px solid #007bff' : '1px solid #ddd', borderRadius: '6px' }}>
                <input
                  type="radio"
                  name="refinement"
                  checked={selectedPromptId === p.id}
                  onChange={() => setSelectedPromptId(p.id)}
                />
                <div>
                  <strong>{p.name}</strong>
                  {p.description && <p style={{ margin: 0, fontSize: '0.85rem', color: '#666' }}>{p.description}</p>}
                </div>
              </label>
            ))}
          </div>

          <button
            onClick={handleRun}
            disabled={loading || !selectedPromptId}
            style={{ padding: '0.75rem 2rem', fontSize: '1rem', background: '#28a745', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            {loading ? 'Running Pipeline...' : 'Run Pipeline'}
          </button>
        </>
      )}

      {error && <p style={{ color: 'red', marginTop: '1rem' }}>Error: {error}</p>}

      {result && (
        <div style={{ marginTop: '1rem' }}>
          <div style={{
            padding: '1.5rem',
            borderRadius: '8px',
            background: result.validation_decision === 'APPROVE' ? '#d4edda' : '#f8d7da',
            border: `2px solid ${result.validation_decision === 'APPROVE' ? '#28a745' : '#dc3545'}`,
            marginBottom: '1rem',
          }}>
            <h2 style={{ color: result.validation_decision === 'APPROVE' ? '#155724' : '#721c24' }}>
              {result.validation_decision === 'APPROVE'
                ? 'APPROVED — Pushed to CMS'
                : 'REJECTED — Story Killed'}
            </h2>
          </div>

          {result.refinement_output && (
            <div style={{ marginBottom: '1rem' }}>
              <h3>Refinement Output</h3>
              <pre style={{ background: '#f9f9f9', padding: '1rem', borderRadius: '6px', whiteSpace: 'pre-wrap', border: '1px solid #ddd' }}>
                {result.refinement_output}
              </pre>
            </div>
          )}

          {result.amy_bot_output && (
            <div style={{ marginBottom: '1rem' }}>
              <h3>Amy Bot Review</h3>
              <pre style={{ background: '#f9f9f9', padding: '1rem', borderRadius: '6px', whiteSpace: 'pre-wrap', border: '1px solid #ddd' }}>
                {result.amy_bot_output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default PipelinePage
