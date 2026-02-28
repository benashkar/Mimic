import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '../api/client'

function BatchResultsPage() {
  const [items, setItems] = useState([])
  const [initialized, setInitialized] = useState(false)
  const pollRefs = useRef({})

  useEffect(() => {
    // Read queued items from sessionStorage
    const raw = sessionStorage.getItem('mimic_batch_queue')
    if (!raw) {
      setInitialized(true)
      return
    }

    let queue
    try {
      queue = JSON.parse(raw)
    } catch {
      setInitialized(true)
      return
    }

    sessionStorage.removeItem('mimic_batch_queue')

    // Initialize items with pending status
    const initial = queue.map((q, i) => ({
      id: i,
      storyId: q.storyId,
      sourceBody: q.sourceBody,
      refinementPromptId: q.refinementPromptId,
      promptName: q.promptName,
      pipelineStoryId: null,
      status: 'starting',
      error: null,
      result: null,
    }))
    setItems(initial)
    setInitialized(true)

    // Fire all pipelines in parallel
    initial.forEach((item) => {
      firePipeline(item)
    })

    return () => {
      // Cleanup all polling intervals
      Object.values(pollRefs.current).forEach(clearInterval)
    }
  }, [])

  async function firePipeline(item) {
    try {
      const data = await apiClient('/pipeline/run', {
        method: 'POST',
        body: JSON.stringify({
          story_id: parseInt(item.storyId, 10),
          selected_story: item.sourceBody,
          refinement_prompt_id: item.refinementPromptId,
        }),
      })

      setItems((prev) =>
        prev.map((it) =>
          it.id === item.id
            ? { ...it, pipelineStoryId: data.story_id, status: 'running' }
            : it
        )
      )

      // Start polling
      pollRefs.current[item.id] = setInterval(async () => {
        try {
          const status = await apiClient(`/pipeline/status/${data.story_id}`)
          if (status.status === 'completed') {
            clearInterval(pollRefs.current[item.id])
            setItems((prev) =>
              prev.map((it) =>
                it.id === item.id
                  ? { ...it, status: 'completed', result: status }
                  : it
              )
            )
          } else if (status.status === 'failed') {
            clearInterval(pollRefs.current[item.id])
            const failedRun = (status.runs || []).find((r) => r.status === 'failed')
            setItems((prev) =>
              prev.map((it) =>
                it.id === item.id
                  ? { ...it, status: 'failed', error: failedRun ? failedRun.error_message : 'Pipeline failed', result: status }
                  : it
              )
            )
          }
        } catch (err) {
          clearInterval(pollRefs.current[item.id])
          setItems((prev) =>
            prev.map((it) =>
              it.id === item.id
                ? { ...it, status: 'failed', error: err.message }
                : it
            )
          )
        }
      }, 2000)
    } catch (err) {
      setItems((prev) =>
        prev.map((it) =>
          it.id === item.id
            ? { ...it, status: 'failed', error: err.message }
            : it
        )
      )
    }
  }

  if (!initialized) return <p>Loading...</p>

  if (items.length === 0) {
    return (
      <div>
        <h1>Batch Results</h1>
        <p>No items queued. Go to <Link to="/prompts">Prompts</Link> and run a source list first.</p>
      </div>
    )
  }

  const completed = items.filter((it) => it.status === 'completed')
  const running = items.filter((it) => it.status === 'running' || it.status === 'starting')
  const failed = items.filter((it) => it.status === 'failed')

  return (
    <div>
      <h1>Batch Pipeline Results</h1>
      <p style={{ color: '#666', marginBottom: '1rem' }}>
        {completed.length} completed, {running.length} running, {failed.length} failed
        {' '}&mdash; {items.length} total
      </p>

      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {items.map((item) => (
          <div
            key={item.id}
            style={{
              padding: '1rem',
              borderRadius: '6px',
              border: item.status === 'completed'
                ? `2px solid ${item.result?.validation_decision === 'APPROVE' ? '#28a745' : '#dc3545'}`
                : item.status === 'failed'
                  ? '2px solid #dc3545'
                  : '1px solid #ddd',
              background: item.status === 'running' || item.status === 'starting'
                ? '#fff9e6'
                : item.status === 'completed' && item.result?.validation_decision === 'APPROVE'
                  ? '#d4edda'
                  : item.status === 'completed'
                    ? '#f8d7da'
                    : item.status === 'failed'
                      ? '#f8d7da'
                      : '#fff',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.25rem' }}>
                  <span style={{
                    display: 'inline-block',
                    padding: '0.15rem 0.5rem',
                    borderRadius: '3px',
                    fontSize: '0.75rem',
                    fontWeight: 'bold',
                    color: '#fff',
                    background: item.promptName.toLowerCase().includes('papa') ? '#007bff' : '#6f42c1',
                  }}>
                    {item.promptName}
                  </span>
                  {item.status === 'starting' && <span style={{ color: '#856404', fontSize: '0.85rem' }}>Starting...</span>}
                  {item.status === 'running' && <span style={{ color: '#856404', fontSize: '0.85rem' }}>Running...</span>}
                  {item.status === 'completed' && (
                    <span style={{
                      fontWeight: 'bold',
                      fontSize: '0.85rem',
                      color: item.result?.validation_decision === 'APPROVE' ? '#155724' : '#721c24',
                    }}>
                      {item.result?.validation_decision === 'APPROVE' ? 'APPROVED' : 'REJECTED'}
                    </span>
                  )}
                  {item.status === 'failed' && <span style={{ color: '#721c24', fontSize: '0.85rem' }}>Failed</span>}
                </div>
                <p style={{ margin: '0.25rem 0', fontSize: '0.85rem', color: '#555', maxHeight: '3em', overflow: 'hidden' }}>
                  {item.sourceBody.substring(0, 200)}{item.sourceBody.length > 200 ? '...' : ''}
                </p>
                {item.error && (
                  <p style={{ margin: '0.25rem 0', fontSize: '0.85rem', color: '#dc3545' }}>{item.error}</p>
                )}
              </div>
              {item.status === 'completed' && item.pipelineStoryId && (
                <Link
                  to={`/stories`}
                  style={{
                    padding: '0.25rem 0.75rem',
                    background: '#007bff',
                    color: '#fff',
                    textDecoration: 'none',
                    borderRadius: '4px',
                    fontSize: '0.85rem',
                    flexShrink: 0,
                  }}
                >
                  View
                </Link>
              )}
            </div>

            {item.status === 'completed' && item.result?.refinement_output && (
              <details style={{ marginTop: '0.5rem' }}>
                <summary style={{ cursor: 'pointer', fontSize: '0.85rem', color: '#007bff' }}>
                  Show Refinement Output
                </summary>
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem', marginTop: '0.25rem', maxHeight: '200px', overflow: 'auto', background: '#f9f9f9', padding: '0.5rem', borderRadius: '4px' }}>
                  {item.result.refinement_output}
                </pre>
              </details>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default BatchResultsPage
