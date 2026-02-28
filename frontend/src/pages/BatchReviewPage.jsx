import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { apiClient } from '../api/client'
import { parseSources, findEnrichment, LinkifiedText } from '../utils/sourceParser'

function BatchReviewPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // stories param: comma-separated storyId:promptName pairs
  // e.g. ?stories=42:Michigan+Source+List,43:Ohio+Source+List
  const storiesParam = searchParams.get('stories') || ''

  const [storyGroups, setStoryGroups] = useState([])
  const [refinementPrompts, setRefinementPrompts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Per-source selections: key = "storyId-sourceIndex", value = refinementPromptId or null (skip)
  const [selections, setSelections] = useState({})

  // Pipeline execution state
  const [executing, setExecuting] = useState(false)
  const [executionResults, setExecutionResults] = useState({}) // key = "storyId-sourceIndex", value = { status, error, pipelineStoryId, result }

  useEffect(() => {
    if (!storiesParam) {
      setLoading(false)
      return
    }

    const entries = storiesParam.split(',').map((entry) => {
      const colonIdx = entry.indexOf(':')
      if (colonIdx === -1) return { storyId: parseInt(entry, 10), promptName: '' }
      return {
        storyId: parseInt(entry.substring(0, colonIdx), 10),
        promptName: decodeURIComponent(entry.substring(colonIdx + 1)),
      }
    }).filter((e) => !isNaN(e.storyId))

    // Fetch refinement prompts and all story statuses in parallel
    Promise.all([
      apiClient('/prompts?type=papa').catch(() => []),
      ...entries.map((e) =>
        apiClient(`/pipeline/status/${e.storyId}`)
          .then((data) => ({ ...e, data, error: null }))
          .catch((err) => ({ ...e, data: null, error: err.message }))
      ),
    ]).then(([refPrompts, ...storyResults]) => {
      setRefinementPrompts(refPrompts)

      const groups = storyResults.map((sr) => {
        if (sr.error || !sr.data) {
          return {
            storyId: sr.storyId,
            promptName: sr.promptName,
            error: sr.error || 'No data',
            sources: [],
            enrichments: null,
          }
        }

        let enrichments = null
        if (sr.data.url_enrichments) {
          try {
            enrichments = JSON.parse(sr.data.url_enrichments)
          } catch (_) { /* ignore */ }
        }

        return {
          storyId: sr.storyId,
          promptName: sr.promptName,
          opportunity: sr.data.opportunity,
          state: sr.data.state,
          error: null,
          sources: parseSources(sr.data.source_list_output),
          rawOutput: sr.data.source_list_output,
          enrichments,
        }
      })

      setStoryGroups(groups)
      setLoading(false)
    })
  }, [storiesParam])

  function setSelection(storyId, sourceIndex, refinementPromptId) {
    const key = `${storyId}-${sourceIndex}`
    setSelections((prev) => {
      // Toggle: if same value, remove selection (skip)
      if (prev[key] === refinementPromptId) {
        const next = { ...prev }
        delete next[key]
        return next
      }
      return { ...prev, [key]: refinementPromptId }
    })
  }

  function selectAllWithPrompt(refinementPromptId) {
    const next = {}
    for (const group of storyGroups) {
      for (let i = 0; i < group.sources.length; i++) {
        next[`${group.storyId}-${i}`] = refinementPromptId
      }
    }
    setSelections(next)
  }

  function clearAllSelections() {
    setSelections({})
  }

  const selectedCount = Object.keys(selections).length
  const totalSources = storyGroups.reduce((sum, g) => sum + g.sources.length, 0)

  async function handleRunAll() {
    if (selectedCount === 0) return
    setExecuting(true)

    // Build queue from selections
    const queue = Object.entries(selections).map(([key, refinementPromptId]) => {
      const [storyIdStr, sourceIndexStr] = key.split('-')
      const storyId = parseInt(storyIdStr, 10)
      const sourceIndex = parseInt(sourceIndexStr, 10)
      const group = storyGroups.find((g) => g.storyId === storyId)
      const source = group?.sources[sourceIndex]
      const refPrompt = refinementPrompts.find((rp) => rp.id === refinementPromptId)
      return {
        key,
        storyId,
        sourceBody: source?.body || '',
        refinementPromptId,
        promptName: refPrompt?.name || '',
      }
    })

    // Initialize all as starting
    const initial = {}
    queue.forEach((q) => {
      initial[q.key] = { status: 'starting', error: null, pipelineStoryId: null, result: null }
    })
    setExecutionResults(initial)

    // Fire all pipelines in parallel
    await Promise.allSettled(queue.map(async (q) => {
      try {
        const data = await apiClient('/pipeline/run', {
          method: 'POST',
          body: JSON.stringify({
            story_id: q.storyId,
            selected_story: q.sourceBody.substring(0, 2000),
            refinement_prompt_id: q.refinementPromptId,
          }),
        })

        setExecutionResults((prev) => ({
          ...prev,
          [q.key]: { ...prev[q.key], status: 'running', pipelineStoryId: data.story_id },
        }))

        // Poll for completion
        await pollForResult(q.key, data.story_id)
      } catch (err) {
        setExecutionResults((prev) => ({
          ...prev,
          [q.key]: { ...prev[q.key], status: 'failed', error: err.message },
        }))
      }
    }))

    setExecuting(false)
  }

  function pollForResult(key, pipelineStoryId) {
    return new Promise((resolve) => {
      const interval = setInterval(async () => {
        try {
          const status = await apiClient(`/pipeline/status/${pipelineStoryId}`)
          if (status.status === 'completed') {
            clearInterval(interval)
            setExecutionResults((prev) => ({
              ...prev,
              [key]: { ...prev[key], status: 'completed', result: status },
            }))
            resolve()
          } else if (status.status === 'failed') {
            clearInterval(interval)
            const failedRun = (status.runs || []).find((r) => r.status === 'failed')
            setExecutionResults((prev) => ({
              ...prev,
              [key]: { ...prev[key], status: 'failed', error: failedRun ? failedRun.error_message : 'Failed', result: status },
            }))
            resolve()
          }
        } catch (err) {
          clearInterval(interval)
          setExecutionResults((prev) => ({
            ...prev,
            [key]: { ...prev[key], status: 'failed', error: err.message },
          }))
          resolve()
        }
      }, 2000)
    })
  }

  const hasExecutionResults = Object.keys(executionResults).length > 0

  if (!storiesParam) {
    return (
      <div>
        <h1>Batch Review</h1>
        <p>No stories to review. Go to <Link to="/prompts">Prompts</Link> and run source lists first.</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div>
        <h1>Batch Review</h1>
        <p>Loading source list results...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <h1>Batch Review</h1>
        <p style={{ color: 'red' }}>Error: {error}</p>
      </div>
    )
  }

  return (
    <div style={{ paddingBottom: selectedCount > 0 && !hasExecutionResults ? '80px' : '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h1 style={{ margin: 0 }}>Batch Review</h1>
        <Link to="/prompts" style={{ fontSize: '0.9rem' }}>Back to Prompts</Link>
      </div>

      <p style={{ color: '#666', marginBottom: '0.75rem' }}>
        {totalSources} source{totalSources !== 1 ? 's' : ''} found across {storyGroups.length} prompt{storyGroups.length !== 1 ? 's' : ''}.
        Select PAPA or PSST for each source you want to refine, or leave unselected to skip.
      </p>

      {!hasExecutionResults && refinementPrompts.length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.85rem', color: '#666' }}>Quick select all:</span>
          {refinementPrompts.map((rp) => (
            <button
              key={rp.id}
              onClick={() => selectAllWithPrompt(rp.id)}
              style={{
                padding: '0.3rem 0.75rem',
                fontSize: '0.85rem',
                background: '#e9ecef',
                border: '1px solid #ced4da',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              All {rp.name}
            </button>
          ))}
          {selectedCount > 0 && (
            <button
              onClick={clearAllSelections}
              style={{
                padding: '0.3rem 0.75rem',
                fontSize: '0.85rem',
                background: '#fff',
                border: '1px solid #ced4da',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Clear All
            </button>
          )}
        </div>
      )}

      {storyGroups.map((group) => (
        <div key={group.storyId} style={{ marginBottom: '2rem' }}>
          <h2 style={{
            margin: '0 0 0.5rem',
            padding: '0.5rem 0',
            borderBottom: '2px solid #007bff',
            fontSize: '1.1rem',
          }}>
            {group.promptName || `Story #${group.storyId}`}
            {group.opportunity && (
              <span style={{ fontWeight: 'normal', fontSize: '0.9rem', color: '#666', marginLeft: '0.75rem' }}>
                {group.opportunity}{group.state ? `, ${group.state}` : ''}
              </span>
            )}
          </h2>

          {group.error && (
            <p style={{ color: 'red', fontSize: '0.9rem' }}>Failed to load: {group.error}</p>
          )}

          {group.sources.length === 0 && !group.error && (
            <p style={{ color: '#888', fontSize: '0.9rem' }}>No sources parsed from this result.</p>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {group.sources.map((source, i) => {
              const key = `${group.storyId}-${i}`
              const selectedRefId = selections[key]
              const enrichment = findEnrichment(source.body, group.enrichments)
              const execResult = executionResults[key]

              return (
                <div
                  key={i}
                  style={{
                    padding: '0.75rem 1rem',
                    borderRadius: '6px',
                    border: execResult?.status === 'completed'
                      ? `2px solid ${execResult.result?.validation_decision === 'APPROVE' ? '#28a745' : '#dc3545'}`
                      : selectedRefId
                        ? '2px solid #007bff'
                        : '1px solid #ddd',
                    background: execResult?.status === 'completed'
                      ? (execResult.result?.validation_decision === 'APPROVE' ? '#d4edda' : '#f8d7da')
                      : execResult?.status === 'running' || execResult?.status === 'starting'
                        ? '#fff9e6'
                        : execResult?.status === 'failed'
                          ? '#f8d7da'
                          : enrichment?.type === 'twitter'
                            ? '#e8f4fd'
                            : enrichment?.type === 'website'
                              ? '#e8f5e9'
                              : '#f9f9f9',
                  }}
                >
                  <div style={{ fontWeight: 'bold', fontSize: '0.9rem', marginBottom: '0.4rem', color: '#333' }}>
                    {i + 1}. {source.label}
                  </div>

                  {enrichment?.type === 'twitter' && (
                    <div style={{ margin: '0.4rem 0', padding: '0.5rem', background: '#fff', borderRadius: '4px', border: '1px solid #b3d9f2' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                        <span style={{ fontWeight: 'bold', color: '#1da1f2' }}>@{enrichment.author_name}</span>
                        {enrichment.created_at && (
                          <span style={{ fontSize: '0.8rem', color: '#888' }}>
                            {new Date(enrichment.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                          </span>
                        )}
                      </div>
                      <p style={{ margin: '0 0 0.25rem', fontSize: '0.85rem', color: '#333' }}>{enrichment.text}</p>
                      <a href={enrichment.url} target="_blank" rel="noopener noreferrer" style={{ color: '#1da1f2', fontSize: '0.8rem' }}>{enrichment.url}</a>
                    </div>
                  )}

                  {enrichment?.type === 'website' && (
                    <div style={{ margin: '0.4rem 0', padding: '0.5rem', background: '#fff', borderRadius: '4px', border: '1px solid #a5d6a7' }}>
                      {enrichment.title && <div style={{ fontWeight: 'bold', marginBottom: '0.25rem', color: '#2e7d32' }}>{enrichment.title}</div>}
                      <p style={{ margin: '0 0 0.25rem', fontSize: '0.8rem', color: '#555' }}>{enrichment.text}</p>
                      <a href={enrichment.url} target="_blank" rel="noopener noreferrer" style={{ color: '#2e7d32', fontSize: '0.8rem' }}>{enrichment.url}</a>
                    </div>
                  )}

                  {!enrichment && (
                    <pre style={{ whiteSpace: 'pre-wrap', margin: '0.4rem 0', fontSize: '0.8rem', color: '#555', maxHeight: '120px', overflow: 'auto' }}>
                      <LinkifiedText text={source.body} />
                    </pre>
                  )}

                  {/* Selection buttons or execution status */}
                  {execResult ? (
                    <div style={{ marginTop: '0.4rem', display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.85rem' }}>
                      <span style={{
                        display: 'inline-block',
                        padding: '0.15rem 0.5rem',
                        borderRadius: '3px',
                        fontSize: '0.75rem',
                        fontWeight: 'bold',
                        color: '#fff',
                        background: (refinementPrompts.find((rp) => rp.id === selectedRefId)?.name || '').toLowerCase().includes('papa') ? '#007bff' : '#6f42c1',
                      }}>
                        {refinementPrompts.find((rp) => rp.id === selectedRefId)?.name || 'Pipeline'}
                      </span>
                      {(execResult.status === 'starting' || execResult.status === 'running') && (
                        <span style={{ color: '#856404' }}>Running...</span>
                      )}
                      {execResult.status === 'completed' && (
                        <span style={{
                          fontWeight: 'bold',
                          color: execResult.result?.validation_decision === 'APPROVE' ? '#155724' : '#721c24',
                        }}>
                          {execResult.result?.validation_decision === 'APPROVE' ? 'APPROVED' : 'REJECTED'}
                        </span>
                      )}
                      {execResult.status === 'failed' && (
                        <span style={{ color: '#721c24' }}>Failed: {execResult.error}</span>
                      )}
                      {execResult.status === 'completed' && execResult.result?.refinement_output && (
                        <details style={{ marginLeft: '0.5rem' }}>
                          <summary style={{ cursor: 'pointer', color: '#007bff', fontSize: '0.8rem' }}>Show Output</summary>
                          <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.75rem', marginTop: '0.25rem', maxHeight: '150px', overflow: 'auto', background: '#fff', padding: '0.5rem', borderRadius: '4px', border: '1px solid #ddd' }}>
                            {execResult.result.refinement_output}
                          </pre>
                        </details>
                      )}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.4rem', alignItems: 'center' }}>
                      {refinementPrompts.map((rp) => {
                        const isSelected = selectedRefId === rp.id
                        const isPapa = rp.name.toLowerCase().includes('papa')
                        return (
                          <button
                            key={rp.id}
                            onClick={() => setSelection(group.storyId, i, rp.id)}
                            style={{
                              padding: '0.35rem 0.9rem',
                              fontSize: '0.85rem',
                              background: isSelected ? (isPapa ? '#007bff' : '#6f42c1') : '#e9ecef',
                              color: isSelected ? '#fff' : '#333',
                              border: isSelected ? 'none' : '1px solid #ced4da',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              fontWeight: isSelected ? 'bold' : 'normal',
                            }}
                          >
                            {rp.name}
                          </button>
                        )
                      })}
                      {selectedRefId && (
                        <span style={{ fontSize: '0.8rem', color: '#28a745', fontWeight: 'bold', marginLeft: '0.25rem' }}>
                          Selected
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {/* Floating action bar when sources are selected and not yet executing */}
      {selectedCount > 0 && !hasExecutionResults && (
        <div style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          background: '#333',
          color: '#fff',
          padding: '0.75rem 1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          zIndex: 1000,
          boxShadow: '0 -2px 8px rgba(0,0,0,0.3)',
        }}>
          <span style={{ fontSize: '0.95rem' }}>
            <strong>{selectedCount}</strong> of {totalSources} source{totalSources !== 1 ? 's' : ''} selected for refinement
          </span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={clearAllSelections}
              style={{ padding: '0.5rem 1rem', background: '#6c757d', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              Clear
            </button>
            <button
              onClick={handleRunAll}
              disabled={executing}
              style={{
                padding: '0.5rem 1.5rem',
                background: executing ? '#6c757d' : '#28a745',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                cursor: executing ? 'not-allowed' : 'pointer',
                fontWeight: 'bold',
              }}
            >
              {executing ? 'Running...' : `Run All (${selectedCount})`}
            </button>
          </div>
        </div>
      )}

      {/* Summary when execution is complete */}
      {hasExecutionResults && !executing && Object.values(executionResults).every((r) => r.status === 'completed' || r.status === 'failed') && (
        <div style={{
          marginTop: '1rem',
          padding: '1rem',
          background: '#f4f4f4',
          borderRadius: '6px',
          border: '1px solid #ddd',
          textAlign: 'center',
        }}>
          <p style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>
            <strong>Batch Complete:</strong>{' '}
            {Object.values(executionResults).filter((r) => r.status === 'completed' && r.result?.validation_decision === 'APPROVE').length} approved,{' '}
            {Object.values(executionResults).filter((r) => r.status === 'completed' && r.result?.validation_decision !== 'APPROVE').length} rejected,{' '}
            {Object.values(executionResults).filter((r) => r.status === 'failed').length} failed
          </p>
          <Link to="/prompts" style={{ color: '#007bff' }}>Back to Prompts</Link>
          {' | '}
          <Link to="/stories" style={{ color: '#007bff' }}>View Stories</Link>
        </div>
      )}
    </div>
  )
}

export default BatchReviewPage
