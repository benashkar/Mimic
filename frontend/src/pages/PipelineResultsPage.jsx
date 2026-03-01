import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { apiClient } from '../api/client'
import { LinkifiedText } from '../utils/sourceParser'

function PipelineResultsPage() {
  const [searchParams] = useSearchParams()
  const storiesParam = searchParams.get('stories') || ''

  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [retrying, setRetrying] = useState(new Set())

  // Filters
  const [statusFilter, setStatusFilter] = useState('all') // all, approved, rejected
  const [searchText, setSearchText] = useState('')
  const [agencyFilter, setAgencyFilter] = useState('')

  useEffect(() => {
    if (!storiesParam) {
      setLoading(false)
      return
    }

    const storyIds = storiesParam.split(',').map((s) => parseInt(s, 10)).filter((n) => !isNaN(n))

    Promise.all(
      storyIds.map((id) =>
        apiClient(`/pipeline/status/${id}`)
          .then((data) => ({ ...data, fetchError: null }))
          .catch((err) => ({ story_id: id, fetchError: err.message }))
      )
    ).then((data) => {
      setResults(data)
      setLoading(false)
    })
  }, [storiesParam])

  async function handleRetry(result) {
    const storyId = result.story_id
    setRetrying((prev) => new Set(prev).add(storyId))

    try {
      const data = await apiClient('/pipeline/run', {
        method: 'POST',
        body: JSON.stringify({
          story_id: storyId,
          selected_story: result.selected_story,
          refinement_prompt_id: result.refinement_prompt_id,
        }),
      })

      // Poll for completion
      const newStoryId = data.story_id
      const poll = setInterval(async () => {
        try {
          const status = await apiClient(`/pipeline/status/${newStoryId}`)
          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(poll)
            setResults((prev) =>
              prev.map((r) => (r.story_id === storyId ? { ...status, fetchError: null } : r))
            )
            setRetrying((prev) => { const next = new Set(prev); next.delete(storyId); return next })
          }
        } catch {
          clearInterval(poll)
          setRetrying((prev) => { const next = new Set(prev); next.delete(storyId); return next })
        }
      }, 2000)
    } catch (err) {
      setRetrying((prev) => { const next = new Set(prev); next.delete(storyId); return next })
    }
  }

  if (!storiesParam) {
    return (
      <div>
        <h1>Pipeline Results</h1>
        <p>No stories specified. Go to <Link to="/prompts">Prompts</Link> to run source lists.</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div>
        <h1>Pipeline Results</h1>
        <p>Loading results...</p>
      </div>
    )
  }

  // Derive agencies from results for filter dropdown
  const allAgencies = [...new Set(
    results.filter((r) => r.opportunity).map((r) => r.opportunity)
  )].sort()

  // Apply filters
  function filterResults(list) {
    return list.filter((r) => {
      if (statusFilter === 'approved' && r.validation_decision !== 'APPROVE') return false
      if (statusFilter === 'rejected' && r.validation_decision === 'APPROVE') return false
      if (agencyFilter && (r.opportunity || '') !== agencyFilter) return false
      if (searchText) {
        const q = searchText.toLowerCase()
        const haystack = [
          r.selected_story,
          r.refinement_output,
          r.opportunity,
          r.state,
          r.publications,
        ].filter(Boolean).join(' ').toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }

  const filtered = filterResults(results)
  const approved = filtered.filter((r) => r.validation_decision === 'APPROVE')
  const rejected = filtered.filter((r) => r.validation_decision !== 'APPROVE' && !r.fetchError)
  const failed = filtered.filter((r) => r.fetchError)

  const totalApproved = results.filter((r) => r.validation_decision === 'APPROVE').length
  const totalRejected = results.filter((r) => r.validation_decision !== 'APPROVE' && !r.fetchError).length

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h1 style={{ margin: 0 }}>Pipeline Results</h1>
        <Link to="/prompts" style={{ fontSize: '0.9rem' }}>Back to Prompts</Link>
      </div>

      <p style={{ color: '#666', marginBottom: '0.75rem' }}>
        {results.length} pipeline{results.length !== 1 ? 's' : ''} run —{' '}
        <span style={{ color: '#155724', fontWeight: 'bold' }}>{totalApproved} approved</span>,{' '}
        <span style={{ color: '#721c24', fontWeight: 'bold' }}>{totalRejected} rejected</span>
      </p>

      {/* Filter controls */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '0.25rem', background: '#f4f4f4', borderRadius: '6px', padding: '0.2rem' }}>
          {[
            { value: 'all', label: `All (${results.length})` },
            { value: 'approved', label: `Approved (${totalApproved})` },
            { value: 'rejected', label: `Rejected (${totalRejected})` },
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value)}
              style={{
                padding: '0.35rem 0.75rem',
                fontSize: '0.85rem',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                background: statusFilter === opt.value ? '#007bff' : 'transparent',
                color: statusFilter === opt.value ? '#fff' : '#333',
                fontWeight: statusFilter === opt.value ? 'bold' : 'normal',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <input
          type="text"
          placeholder="Search results..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ padding: '0.4rem 0.6rem', flex: 1, maxWidth: '250px', border: '1px solid #ccc', borderRadius: '4px' }}
        />

        {allAgencies.length > 1 && (
          <select
            value={agencyFilter}
            onChange={(e) => setAgencyFilter(e.target.value)}
            style={{ padding: '0.4rem', border: '1px solid #ccc', borderRadius: '4px' }}
          >
            <option value="">All Opportunities</option>
            {allAgencies.map((ag) => (
              <option key={ag} value={ag}>{ag}</option>
            ))}
          </select>
        )}

        {(searchText || agencyFilter || statusFilter !== 'all') && (
          <button
            onClick={() => { setSearchText(''); setAgencyFilter(''); setStatusFilter('all') }}
            style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem', cursor: 'pointer' }}
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Approved section */}
      {approved.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          {statusFilter === 'all' && (
            <h2 style={{ color: '#155724', borderBottom: '2px solid #28a745', paddingBottom: '0.25rem', fontSize: '1.1rem' }}>
              Approved ({approved.length})
            </h2>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {approved.map((r) => (
              <ResultCard key={r.story_id} result={r} retrying={retrying.has(r.story_id)} onRetry={() => handleRetry(r)} />
            ))}
          </div>
        </div>
      )}

      {/* Rejected section */}
      {rejected.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          {statusFilter === 'all' && (
            <h2 style={{ color: '#721c24', borderBottom: '2px solid #dc3545', paddingBottom: '0.25rem', fontSize: '1.1rem' }}>
              Rejected ({rejected.length})
            </h2>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {rejected.map((r) => (
              <ResultCard key={r.story_id} result={r} retrying={retrying.has(r.story_id)} onRetry={() => handleRetry(r)} />
            ))}
          </div>
        </div>
      )}

      {/* Failed section */}
      {failed.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          <h2 style={{ color: '#856404', borderBottom: '2px solid #ffc107', paddingBottom: '0.25rem', fontSize: '1.1rem' }}>
            Failed ({failed.length})
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {failed.map((r) => (
              <div key={r.story_id} style={{ padding: '0.75rem', borderRadius: '6px', border: '1px solid #ffc107', background: '#fff9e6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#856404' }}>Story #{r.story_id}: {r.fetchError}</span>
                {r.selected_story && r.refinement_prompt_id && (
                  <button
                    onClick={() => handleRetry(r)}
                    disabled={retrying.has(r.story_id)}
                    style={{
                      padding: '0.3rem 0.75rem',
                      fontSize: '0.8rem',
                      background: retrying.has(r.story_id) ? '#6c757d' : '#ffc107',
                      color: '#333',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: retrying.has(r.story_id) ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {retrying.has(r.story_id) ? 'Retrying...' : 'Retry'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {filtered.length === 0 && (
        <p style={{ color: '#888', textAlign: 'center', marginTop: '2rem' }}>
          No results match your filters.
        </p>
      )}
    </div>
  )
}

function ResultCard({ result, retrying, onRetry }) {
  const [copiedId, setCopiedId] = useState(null)
  const isApproved = result.validation_decision === 'APPROVE'
  const showRetry = !retrying && (
    result.status === 'failed' || result.fetchError || result.validation_decision !== 'APPROVE'
  ) && result.selected_story && result.refinement_prompt_id

  // Extract refinement type from runs
  const refinementRun = (result.runs || []).find((r) => r.step_type === 'refinement')
  const refinementType = refinementRun ? (refinementRun.step_type === 'refinement' ? 'Refinement' : refinementRun.step_type) : null

  // Try to extract Organization from refinement output
  let organization = null
  if (result.refinement_output) {
    const orgMatch = result.refinement_output.match(/Organization:\s*(.+?)(?:\n|$)/)
    if (orgMatch) organization = orgMatch[1].trim()
  }

  function handleCopy() {
    navigator.clipboard.writeText(result.refinement_output).then(() => {
      setCopiedId(result.story_id)
      setTimeout(() => setCopiedId(null), 2000)
    })
  }

  return (
    <div style={{
      padding: '0.75rem 1rem',
      borderRadius: '6px',
      border: retrying ? '2px solid #ffc107' : `2px solid ${isApproved ? '#28a745' : '#dc3545'}`,
      background: retrying ? '#fff9e6' : (isApproved ? '#d4edda' : '#f8d7da'),
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.4rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{
            fontWeight: 'bold',
            fontSize: '0.9rem',
            color: retrying ? '#856404' : (isApproved ? '#155724' : '#721c24'),
          }}>
            {retrying ? 'RETRYING...' : (isApproved ? 'APPROVED' : 'REJECTED')}
          </span>
          {organization && (
            <span style={{ fontSize: '0.85rem', color: '#555' }}>
              {organization}
            </span>
          )}
          {result.opportunity && (
            <span style={{
              display: 'inline-block',
              padding: '0.1rem 0.4rem',
              borderRadius: '3px',
              fontSize: '0.75rem',
              background: '#e9ecef',
              color: '#495057',
            }}>
              {result.opportunity}{result.state ? `, ${result.state}` : ''}
            </span>
          )}
        </div>
        {showRetry && (
          <button
            onClick={onRetry}
            style={{
              padding: '0.25rem 0.6rem',
              fontSize: '0.8rem',
              background: '#ffc107',
              color: '#333',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 'bold',
            }}
          >
            Retry
          </button>
        )}
      </div>

      {result.selected_story && (
        <div style={{ fontSize: '0.85rem', color: '#333', marginBottom: '0.4rem', maxHeight: '4em', overflow: 'hidden' }}>
          <LinkifiedText text={result.selected_story.substring(0, 300)} />
          {result.selected_story.length > 300 ? '...' : ''}
        </div>
      )}

      {result.refinement_output && (
        <details style={{ marginTop: '0.3rem' }}>
          <summary style={{ cursor: 'pointer', fontSize: '0.85rem', color: '#007bff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            Show Refinement Output
            <button
              onClick={(e) => { e.preventDefault(); handleCopy() }}
              style={{
                padding: '0.15rem 0.5rem',
                fontSize: '0.75rem',
                background: copiedId === result.story_id ? '#28a745' : '#e9ecef',
                color: copiedId === result.story_id ? '#fff' : '#333',
                border: '1px solid #ced4da',
                borderRadius: '3px',
                cursor: 'pointer',
              }}
            >
              {copiedId === result.story_id ? 'Copied!' : 'Copy'}
            </button>
          </summary>
          <pre style={{
            whiteSpace: 'pre-wrap',
            fontSize: '0.8rem',
            marginTop: '0.25rem',
            background: '#fff',
            padding: '0.5rem',
            borderRadius: '4px',
            border: '1px solid #ddd',
          }}>
            {result.refinement_output}
          </pre>
        </details>
      )}

      {result.amy_bot_output && (
        <details style={{ marginTop: '0.3rem' }}>
          <summary style={{ cursor: 'pointer', fontSize: '0.85rem', color: '#6f42c1' }}>
            Show Amy Bot Review
          </summary>
          <pre style={{
            whiteSpace: 'pre-wrap',
            fontSize: '0.8rem',
            marginTop: '0.25rem',
            background: '#fff',
            padding: '0.5rem',
            borderRadius: '4px',
            border: '1px solid #ddd',
          }}>
            {result.amy_bot_output}
          </pre>
        </details>
      )}
    </div>
  )
}

export default PipelineResultsPage
