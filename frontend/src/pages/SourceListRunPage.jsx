import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { parseSources, findEnrichment, LinkifiedText } from '../utils/sourceParser'

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
  const [refinementPrompts, setRefinementPrompts] = useState([])
  const [queue, setQueue] = useState([]) // { sourceIndex, sourceBody, refinementPromptId, promptName }
  const pollRef = useRef(null)

  useEffect(() => {
    if (promptId) {
      apiClient(`/prompts/${promptId}`)
        .then(setPrompt)
        .catch((err) => setError(err.message))
    }
    // Fetch refinement prompts (PAPA/PSST) for inline buttons
    apiClient('/prompts?type=papa')
      .then(setRefinementPrompts)
      .catch(() => {}) // Non-critical
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

  function handleRunPipeline(topicBody, refinementPromptId) {
    navigate(`/pipeline?story_id=${storyId}&selected=${encodeURIComponent(topicBody.substring(0, 2000))}&refinement_prompt_id=${refinementPromptId}`)
  }

  function toggleQueue(sourceIndex, sourceBody, refinementPromptId, promptName) {
    setQueue((prev) => {
      const exists = prev.find((q) => q.sourceIndex === sourceIndex && q.refinementPromptId === refinementPromptId)
      if (exists) {
        return prev.filter((q) => !(q.sourceIndex === sourceIndex && q.refinementPromptId === refinementPromptId))
      }
      return [...prev, { sourceIndex, sourceBody, refinementPromptId, promptName }]
    })
  }

  function isQueued(sourceIndex, refinementPromptId) {
    return queue.some((q) => q.sourceIndex === sourceIndex && q.refinementPromptId === refinementPromptId)
  }

  function handleRunAll() {
    // Navigate to batch results with queued items
    const batchData = queue.map((q) => ({
      storyId,
      sourceBody: q.sourceBody.substring(0, 2000),
      refinementPromptId: q.refinementPromptId,
      promptName: q.promptName,
    }))
    sessionStorage.setItem('mimic_batch_queue', JSON.stringify(batchData))
    navigate('/batch-results')
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
            Click a refinement type to run immediately, or use <strong>+</strong> to queue multiple sources and run them all at once.
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

                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                      {refinementPrompts.length > 0 ? (
                        refinementPrompts.map((rp) => {
                          const queued = isQueued(i, rp.id)
                          return (
                            <div key={rp.id} style={{ display: 'flex', gap: '0.25rem' }}>
                              <button
                                onClick={() => handleRunPipeline(source.body, rp.id)}
                                style={{
                                  padding: '0.4rem 1rem',
                                  fontSize: '0.85rem',
                                  background: '#007bff',
                                  color: '#fff',
                                  border: 'none',
                                  borderRadius: '4px 0 0 4px',
                                  cursor: 'pointer',
                                }}
                                title={`Run ${rp.name} now`}
                              >
                                {rp.name}
                              </button>
                              <button
                                onClick={() => toggleQueue(i, source.body, rp.id, rp.name)}
                                style={{
                                  padding: '0.4rem 0.5rem',
                                  fontSize: '0.85rem',
                                  background: queued ? '#28a745' : '#6c757d',
                                  color: '#fff',
                                  border: 'none',
                                  borderRadius: '0 4px 4px 0',
                                  cursor: 'pointer',
                                }}
                                title={queued ? 'Remove from queue' : `Queue ${rp.name}`}
                              >
                                {queued ? '✓' : '+'}
                              </button>
                            </div>
                          )
                        })
                      ) : (
                        <button
                          onClick={() => navigate(`/pipeline?story_id=${storyId}&selected=${encodeURIComponent(source.body.substring(0, 2000))}`)}
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
                      )}
                    </div>
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

      {queue.length > 0 && (
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
            <strong>{queue.length}</strong> source{queue.length !== 1 ? 's' : ''} queued
          </span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={() => setQueue([])}
              style={{ padding: '0.5rem 1rem', background: '#6c757d', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              Clear
            </button>
            <button
              onClick={handleRunAll}
              style={{ padding: '0.5rem 1.5rem', background: '#28a745', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
            >
              Run All
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default SourceListRunPage
