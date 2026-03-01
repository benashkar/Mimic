import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiClient } from '../api/client'
import { findEnrichment, LinkifiedText } from '../utils/sourceParser'

function QueuePage() {
  const { user } = useAuth()

  const [items, setItems] = useState([])
  const [refinementPrompts, setRefinementPrompts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Per-item selections: key = itemId, value = refinementPromptId
  const [selections, setSelections] = useState({})
  // Discarded items: Set of item IDs
  const [discarded, setDiscarded] = useState(new Set())

  // Execution state: key = itemId, value = { status, error, storyId }
  const [executionResults, setExecutionResults] = useState({})
  const [executing, setExecuting] = useState(false)

  // Per-item source stats
  const [sourceStats, setSourceStats] = useState({})

  // Enrichments by story_id
  const [enrichments, setEnrichments] = useState({})

  useEffect(() => {
    loadQueue()
  }, [])

  async function loadQueue() {
    setLoading(true)
    setError(null)
    try {
      const [queueItems, refPrompts] = await Promise.all([
        apiClient('/queue?status=pending'),
        apiClient('/prompts?type=papa'),
      ])
      setItems(queueItems)
      setRefinementPrompts(refPrompts)

      // Fetch enrichments for each unique story_id
      const storyIds = [...new Set(queueItems.map((i) => i.story_id))]
      const enrichMap = {}
      await Promise.all(storyIds.map(async (storyId) => {
        try {
          const status = await apiClient(`/pipeline/status/${storyId}`)
          if (status.url_enrichments) {
            try {
              enrichMap[storyId] = JSON.parse(status.url_enrichments)
            } catch (_) { /* ignore */ }
          }
        } catch (_) { /* ignore */ }
      }))
      setEnrichments(enrichMap)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Fetch per-source history stats
  useEffect(() => {
    if (items.length === 0) return
    const sources = items.map((item) => item.body.substring(0, 2000))
    const idMap = items.map((item) => item.id)
    apiClient('/stories/source-stats', {
      method: 'POST',
      body: JSON.stringify({ sources }),
    }).then((data) => {
      const mapped = {}
      for (const [idx, stats] of Object.entries(data.stats || {})) {
        mapped[idMap[parseInt(idx, 10)]] = stats
      }
      setSourceStats(mapped)
    }).catch(() => {})
  }, [items])

  // Auto-load last PAPA/PSST choice per opportunity from localStorage
  useEffect(() => {
    if (items.length === 0 || refinementPrompts.length === 0) return
    const autoSelections = {}
    for (const item of items) {
      if (!item.opportunity) continue
      const savedId = localStorage.getItem('mimic_ref_' + item.opportunity)
      if (!savedId) continue
      const savedInt = parseInt(savedId, 10)
      if (!refinementPrompts.some((rp) => rp.id === savedInt)) continue
      autoSelections[item.id] = savedInt
    }
    if (Object.keys(autoSelections).length > 0) {
      setSelections((prev) => ({ ...autoSelections, ...prev }))
    }
  }, [items, refinementPrompts])

  function setSelection(itemId, refinementPromptId) {
    setDiscarded((prev) => { const next = new Set(prev); next.delete(itemId); return next })
    setSelections((prev) => {
      if (prev[itemId] === refinementPromptId) {
        const next = { ...prev }
        delete next[itemId]
        return next
      }
      return { ...prev, [itemId]: refinementPromptId }
    })
    // Remember choice per opportunity
    const item = items.find((i) => i.id === itemId)
    if (item?.opportunity) {
      localStorage.setItem('mimic_ref_' + item.opportunity, refinementPromptId)
    }
  }

  function toggleDiscard(itemId) {
    setSelections((prev) => { const next = { ...prev }; delete next[itemId]; return next })
    setDiscarded((prev) => {
      const next = new Set(prev)
      if (next.has(itemId)) next.delete(itemId)
      else next.add(itemId)
      return next
    })
  }

  function selectAllWithPrompt(refinementPromptId) {
    const next = {}
    for (const item of items) {
      next[item.id] = refinementPromptId
    }
    setSelections(next)
    setDiscarded(new Set())
  }

  function clearAllSelections() {
    setSelections({})
  }

  async function handleDiscard() {
    const ids = Array.from(discarded)
    if (ids.length === 0) return
    try {
      await apiClient('/queue/discard', {
        method: 'POST',
        body: JSON.stringify({ item_ids: ids }),
      })
      setDiscarded(new Set())
      loadQueue()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleRunAll() {
    const selected = Object.entries(selections)
    if (selected.length === 0) return
    setExecuting(true)

    // Initialize all as starting
    const initial = {}
    selected.forEach(([itemId]) => {
      initial[itemId] = { status: 'starting', error: null, storyId: null }
    })
    setExecutionResults(initial)

    try {
      // Build batch request — single API call instead of N individual calls
      const batchItems = selected.map(([itemIdStr, refinementPromptId]) => ({
        item_id: parseInt(itemIdStr, 10),
        refinement_prompt_id: refinementPromptId,
      }))

      const batchData = await apiClient('/queue/execute-batch', {
        method: 'POST',
        body: JSON.stringify({ items: batchItems, max_workers: 5 }),
      })

      // Map item_ids to story_ids from batch response
      const itemStoryMap = {}
      batchData.item_ids.forEach((itemId, idx) => {
        itemStoryMap[itemId] = batchData.story_ids[idx]
      })

      // Update all items to running with their story_ids
      setExecutionResults((prev) => {
        const next = { ...prev }
        for (const itemId of batchData.item_ids) {
          next[itemId] = { status: 'running', error: null, storyId: itemStoryMap[itemId] }
        }
        return next
      })

      // Poll each story for completion
      const storyIds = batchData.story_ids
      await Promise.allSettled(batchData.item_ids.map(async (itemId, idx) => {
        const storyId = storyIds[idx]
        await new Promise((resolve) => {
          const interval = setInterval(async () => {
            try {
              const status = await apiClient(`/pipeline/status/${storyId}`)
              if (status.status === 'completed') {
                clearInterval(interval)
                setExecutionResults((prev) => ({
                  ...prev,
                  [itemId]: { status: 'completed', error: null, storyId, result: status },
                }))
                resolve()
              } else if (status.status === 'failed') {
                clearInterval(interval)
                const failedRun = (status.runs || []).find((r) => r.status === 'failed')
                setExecutionResults((prev) => ({
                  ...prev,
                  [itemId]: { status: 'failed', error: failedRun ? failedRun.error_message : 'Failed', storyId },
                }))
                resolve()
              }
            } catch (err) {
              clearInterval(interval)
              setExecutionResults((prev) => ({
                ...prev,
                [itemId]: { status: 'failed', error: err.message, storyId },
              }))
              resolve()
            }
          }, 2000)
        })
        return storyId
      }))

      setExecuting(false)

      // Auto-navigate to pipeline results with all story IDs
      if (storyIds.length > 0) {
        window.location.href = `/pipeline-results?stories=${storyIds.join(',')}`
      }
    } catch (err) {
      setError(err.message)
      setExecuting(false)
    }
  }

  const selectedCount = Object.keys(selections).length
  const hasExecutionResults = Object.keys(executionResults).length > 0

  // Group items by opportunity
  const grouped = {}
  for (const item of items) {
    const key = item.opportunity || 'Other'
    if (!grouped[key]) grouped[key] = []
    grouped[key].push(item)
  }
  const groupKeys = Object.keys(grouped).sort()

  if (loading) {
    return (
      <div>
        <h1>Review Queue</h1>
        <p>Loading queue...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <h1>Review Queue</h1>
        <p style={{ color: 'red' }}>Error: {error}</p>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div>
        <h1>Review Queue</h1>
        <p style={{ color: '#888' }}>No pending sources to review. Queue is empty.</p>
        <Link to="/prompts" style={{ color: '#007bff' }}>Go to Prompts</Link>
      </div>
    )
  }

  return (
    <div style={{ paddingBottom: selectedCount > 0 && !hasExecutionResults ? '80px' : '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h1 style={{ margin: 0 }}>Review Queue</h1>
        <span style={{ color: '#666', fontSize: '0.9rem' }}>
          {items.length} source{items.length !== 1 ? 's' : ''} pending review
        </span>
      </div>

      <p style={{ color: '#666', marginBottom: '0.75rem', fontSize: '0.9rem' }}>
        Sources discovered by the daily scheduler. Select PAPA or PSST for each source, or Discard to skip.
      </p>

      {/* Quick select all */}
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
          {discarded.size > 0 && (
            <button
              onClick={handleDiscard}
              style={{
                padding: '0.3rem 0.75rem',
                fontSize: '0.85rem',
                background: '#dc3545',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Confirm Discard ({discarded.size})
            </button>
          )}
        </div>
      )}

      {/* Grouped items */}
      {groupKeys.map((oppKey) => (
        <div key={oppKey} style={{ marginBottom: '2rem' }}>
          <h2 style={{
            margin: '0 0 0.5rem',
            padding: '0.5rem 0',
            borderBottom: '2px solid #007bff',
            fontSize: '1.1rem',
          }}>
            {oppKey}
            <span style={{ fontWeight: 'normal', fontSize: '0.85rem', color: '#666', marginLeft: '0.75rem' }}>
              ({grouped[oppKey].length} source{grouped[oppKey].length !== 1 ? 's' : ''})
            </span>
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {grouped[oppKey].map((item, i) => {
              const selectedRefId = selections[item.id]
              const isDiscarded = discarded.has(item.id)
              const storyEnrichments = enrichments[item.story_id] || null
              const enrichment = findEnrichment(item.body, storyEnrichments)
              const execResult = executionResults[item.id]
              const stats = sourceStats[item.id]

              return (
                <div
                  key={item.id}
                  style={{
                    padding: '0.75rem 1rem',
                    borderRadius: '6px',
                    opacity: isDiscarded ? 0.45 : 1,
                    border: execResult?.status === 'completed'
                      ? `2px solid ${execResult.result?.validation_decision === 'APPROVE' ? '#28a745' : '#dc3545'}`
                      : isDiscarded
                        ? '2px solid #dc3545'
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                    <div style={{ fontWeight: 'bold', fontSize: '0.9rem', color: '#333' }}>
                      {i + 1}. {item.label}
                    </div>
                    {stats && (
                      <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.7rem' }}>
                        {stats.papa > 0 && (
                          <span style={{ padding: '0.1rem 0.35rem', borderRadius: '3px', background: '#cce5ff', color: '#004085' }}>
                            PAPA {stats.papa}x
                          </span>
                        )}
                        {stats.psst > 0 && (
                          <span style={{ padding: '0.1rem 0.35rem', borderRadius: '3px', background: '#e2d5f1', color: '#4a235a' }}>
                            PSST {stats.psst}x
                          </span>
                        )}
                        {stats.rejected > 0 && (
                          <span style={{ padding: '0.1rem 0.35rem', borderRadius: '3px', background: '#f8d7da', color: '#721c24' }}>
                            {stats.rejected} rejected
                          </span>
                        )}
                      </div>
                    )}
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
                      <LinkifiedText text={item.body} />
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
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.4rem', alignItems: 'center' }}>
                      {refinementPrompts.map((rp) => {
                        const isSelected = selectedRefId === rp.id
                        const isPapa = rp.name.toLowerCase().includes('papa')
                        return (
                          <button
                            key={rp.id}
                            onClick={() => setSelection(item.id, rp.id)}
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
                      <button
                        onClick={() => toggleDiscard(item.id)}
                        style={{
                          padding: '0.35rem 0.9rem',
                          fontSize: '0.85rem',
                          background: isDiscarded ? '#dc3545' : '#e9ecef',
                          color: isDiscarded ? '#fff' : '#888',
                          border: isDiscarded ? 'none' : '1px solid #ced4da',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontWeight: isDiscarded ? 'bold' : 'normal',
                        }}
                      >
                        Discard
                      </button>
                      {selectedRefId && (
                        <span style={{ fontSize: '0.8rem', color: '#28a745', fontWeight: 'bold', marginLeft: '0.25rem' }}>
                          Selected
                        </span>
                      )}
                      {isDiscarded && (
                        <span style={{ fontSize: '0.8rem', color: '#dc3545', fontWeight: 'bold', marginLeft: '0.25rem' }}>
                          Discarded
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
            <strong>{selectedCount}</strong> of {items.length} source{items.length !== 1 ? 's' : ''} selected for refinement
            {discarded.size > 0 && (
              <span style={{ marginLeft: '0.75rem', color: '#ff8a80' }}>
                ({discarded.size} discarded)
              </span>
            )}
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
            <strong>Queue Run Complete:</strong>{' '}
            {Object.values(executionResults).filter((r) => r.status === 'completed' && r.result?.validation_decision === 'APPROVE').length} approved,{' '}
            {Object.values(executionResults).filter((r) => r.status === 'completed' && r.result?.validation_decision !== 'APPROVE').length} rejected,{' '}
            {Object.values(executionResults).filter((r) => r.status === 'failed').length} failed
          </p>
          <Link to="/" style={{ color: '#007bff' }}>Dashboard</Link>
          {' | '}
          <Link to="/stories" style={{ color: '#007bff' }}>View Stories</Link>
        </div>
      )}
    </div>
  )
}

export default QueuePage
