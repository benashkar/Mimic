import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '../api/client'

function StoriesPage() {
  const [stories, setStories] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedStory, setSelectedStory] = useState(null)

  useEffect(() => {
    loadStories()
  }, [page, filter])

  async function loadStories() {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ page, per_page: 20 })
      if (filter) params.set('decision', filter)
      const data = await apiClient(`/stories?${params}`)
      setStories(data.stories)
      setTotal(data.total)
      setPages(data.pages)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function viewDetail(id) {
    try {
      const data = await apiClient(`/stories/${id}`)
      setSelectedStory(data)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <h1>Stories ({total})</h1>

      <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem' }}>
        {['', 'APPROVE', 'REJECT'].map((f) => (
          <button
            key={f}
            onClick={() => { setFilter(f); setPage(1) }}
            style={{ fontWeight: filter === f ? 'bold' : 'normal', textDecoration: filter === f ? 'underline' : 'none' }}
          >
            {f || 'All'}
          </button>
        ))}
      </div>

      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {loading && <p>Loading...</p>}

      {selectedStory && (
        <StoryDetail story={selectedStory} onClose={() => setSelectedStory(null)} />
      )}

      {!loading && !selectedStory && (
        <>
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            {stories.map((s) => (
              <div
                key={s.id}
                onClick={() => viewDetail(s.id)}
                style={{
                  border: '1px solid #ddd',
                  borderRadius: '6px',
                  padding: '1rem',
                  cursor: 'pointer',
                  borderLeft: `4px solid ${s.validation_decision === 'APPROVE' ? '#28a745' : s.validation_decision === 'REJECT' ? '#dc3545' : '#ffc107'}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <div>
                    <strong>Story #{s.id}</strong>
                    {s.opportunity && <span style={{ color: '#666' }}> | {s.opportunity}</span>}
                    {s.state && <span style={{ color: '#666' }}> | {s.state}</span>}
                  </div>
                  <span style={{
                    padding: '0.25rem 0.75rem',
                    borderRadius: '12px',
                    fontSize: '0.8rem',
                    fontWeight: 'bold',
                    color: '#fff',
                    background: s.validation_decision === 'APPROVE' ? '#28a745' : s.validation_decision === 'REJECT' ? '#dc3545' : '#ffc107',
                  }}>
                    {s.validation_decision || 'PENDING'}
                  </span>
                </div>
                <p style={{ color: '#888', fontSize: '0.85rem', margin: '0.25rem 0 0' }}>
                  {s.created_at ? new Date(s.created_at).toLocaleString() : ''}
                  {s.created_by && ` by ${s.created_by}`}
                </p>
              </div>
            ))}
          </div>

          {stories.length === 0 && <p style={{ color: '#888' }}>No stories yet. Run a pipeline to create one.</p>}

          {pages > 1 && (
            <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
              <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}>Prev</button>
              <span>Page {page} of {pages}</span>
              <button onClick={() => setPage(Math.min(pages, page + 1))} disabled={page >= pages}>Next</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function StoryDetail({ story, onClose }) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <button onClick={onClose} style={{ marginBottom: '1rem' }}>Back to list</button>

      <div style={{
        padding: '1rem',
        borderRadius: '8px',
        background: story.validation_decision === 'APPROVE' ? '#d4edda' : story.validation_decision === 'REJECT' ? '#f8d7da' : '#fff3cd',
        marginBottom: '1rem',
      }}>
        <h2>Story #{story.id} — {story.validation_decision || 'PENDING'}</h2>
        <p>{story.opportunity} | {story.state} | {story.created_by}</p>
      </div>

      {story.source_list_output && (
        <Section title="Source List Output" content={story.source_list_output} />
      )}
      {story.selected_story && (
        <Section title="Selected Story" content={story.selected_story} />
      )}
      {story.refinement_output && (
        <Section title="Refinement Output" content={story.refinement_output} />
      )}
      {story.amy_bot_output && (
        <Section title="Amy Bot Review" content={story.amy_bot_output} />
      )}

      {story.pipeline_runs && story.pipeline_runs.length > 0 && (
        <div style={{ marginTop: '1rem' }}>
          <h3>Pipeline Runs</h3>
          {story.pipeline_runs.map((r) => (
            <div key={r.id} style={{ border: '1px solid #ddd', borderRadius: '4px', padding: '0.5rem', marginBottom: '0.5rem', fontSize: '0.9rem' }}>
              <strong>{r.step_type}</strong> — {r.status}
              {r.duration_ms && <span> ({r.duration_ms}ms)</span>}
              {r.error_message && <p style={{ color: 'red' }}>{r.error_message}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Section({ title, content }) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <h3>{title}</h3>
      <pre style={{ background: '#f9f9f9', padding: '1rem', borderRadius: '6px', whiteSpace: 'pre-wrap', border: '1px solid #ddd', maxHeight: '300px', overflow: 'auto' }}>
        {content}
      </pre>
    </div>
  )
}

export default StoriesPage
