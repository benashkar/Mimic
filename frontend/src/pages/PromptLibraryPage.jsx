import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiClient } from '../api/client'

function PromptLibraryPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [prompts, setPrompts] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editingPrompt, setEditingPrompt] = useState(null)

  // Search / filter
  const [searchText, setSearchText] = useState('')
  const [agencyFilter, setAgencyFilter] = useState('')

  // Batch source list running
  const [selectedPrompts, setSelectedPrompts] = useState(new Set())
  const [batchRunning, setBatchRunning] = useState({}) // { promptId: { storyId, status, error } }
  const batchNavigatedRef = useRef(false)

  const isAdmin = user && user.role === 'admin'

  // Auto-navigate to batch review when all runs finish
  useEffect(() => {
    const entries = Object.entries(batchRunning)
    if (entries.length === 0) return
    if (batchNavigatedRef.current) return

    const anyPending = entries.some(([, r]) => r.status === 'running' || r.status === 'starting')
    if (anyPending) return

    // All done — build URL from completed entries
    const completed = entries
      .filter(([, r]) => r.status === 'completed' && r.storyId)
      .map(([promptId, r]) => {
        const prompt = prompts.find((p) => p.id === parseInt(promptId, 10))
        const name = prompt ? encodeURIComponent(prompt.name) : ''
        return `${r.storyId}:${name}`
      })

    if (completed.length > 0) {
      batchNavigatedRef.current = true
      navigate(`/batch-review?stories=${completed.join(',')}`)
    }
  }, [batchRunning, prompts, navigate])

  useEffect(() => {
    loadPrompts()
  }, [filter])

  async function loadPrompts() {
    setLoading(true)
    setError(null)
    try {
      const params = filter !== 'all' ? `?type=${filter}` : ''
      const data = await apiClient(`/prompts${params}`)
      setPrompts(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('Deactivate this prompt?')) return
    try {
      await apiClient(`/prompts/${id}`, { method: 'DELETE' })
      loadPrompts()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleSave(formData) {
    try {
      if (editingPrompt) {
        await apiClient(`/prompts/${editingPrompt.id}`, {
          method: 'PUT',
          body: JSON.stringify(formData),
        })
      } else {
        await apiClient('/prompts', {
          method: 'POST',
          body: JSON.stringify(formData),
        })
      }
      setShowForm(false)
      setEditingPrompt(null)
      loadPrompts()
    } catch (err) {
      setError(err.message)
    }
  }

  function togglePromptSelection(id) {
    setSelectedPrompts((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectAllSourceLists() {
    const filtered = filterPrompts(prompts.filter((p) => p.prompt_type === 'source-list'))
    const slIds = filtered.map((p) => p.id)
    setSelectedPrompts((prev) => {
      const allSelected = slIds.every((id) => prev.has(id))
      if (allSelected) return new Set() // deselect all
      return new Set(slIds)
    })
  }

  async function handleRunSelected() {
    if (selectedPrompts.size === 0) return
    const ids = Array.from(selectedPrompts)

    // Fire all source list runs in parallel
    const newRunning = {}
    ids.forEach((id) => { newRunning[id] = { storyId: null, status: 'starting', error: null } })
    setBatchRunning((prev) => ({ ...prev, ...newRunning }))

    await Promise.allSettled(ids.map(async (promptId) => {
      try {
        const data = await apiClient('/pipeline/source-list', {
          method: 'POST',
          body: JSON.stringify({ prompt_id: promptId }),
        })
        setBatchRunning((prev) => ({
          ...prev,
          [promptId]: { storyId: data.story_id, status: 'running', error: null },
        }))
        // Start polling for this prompt's story
        pollBatchStatus(promptId, data.story_id)
      } catch (err) {
        setBatchRunning((prev) => ({
          ...prev,
          [promptId]: { storyId: null, status: 'failed', error: err.message },
        }))
      }
    }))

    setSelectedPrompts(new Set())
  }

  function pollBatchStatus(promptId, storyId) {
    const interval = setInterval(async () => {
      try {
        const status = await apiClient(`/pipeline/status/${storyId}`)
        if (status.status === 'completed') {
          clearInterval(interval)
          setBatchRunning((prev) => ({
            ...prev,
            [promptId]: { storyId, status: 'completed', error: null },
          }))
        } else if (status.status === 'failed') {
          clearInterval(interval)
          const failedRun = (status.runs || []).find((r) => r.status === 'failed')
          setBatchRunning((prev) => ({
            ...prev,
            [promptId]: { storyId, status: 'failed', error: failedRun ? failedRun.error_message : 'Failed' },
          }))
        }
      } catch (err) {
        clearInterval(interval)
        setBatchRunning((prev) => ({
          ...prev,
          [promptId]: { storyId, status: 'failed', error: err.message },
        }))
      }
    }, 2000)
  }

  // Derive distinct agencies from loaded prompts for filter dropdown
  const allAgencies = [...new Set(
    prompts.filter((p) => p.agency).map((p) => p.agency)
  )].sort()

  // Apply search/agency filter client-side
  function filterPrompts(list) {
    return list.filter((p) => {
      if (agencyFilter && (p.agency || '').toLowerCase() !== agencyFilter.toLowerCase()) return false
      if (searchText) {
        const q = searchText.toLowerCase()
        const haystack = [p.name, p.agency, p.opportunity, p.description].filter(Boolean).join(' ').toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }

  const sourceLists = filterPrompts(prompts.filter((p) => p.prompt_type === 'source-list'))
  const refinement = filterPrompts(prompts.filter((p) => p.prompt_type === 'papa'))
  const amyBots = filterPrompts(prompts.filter((p) => p.prompt_type === 'amy-bot'))

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Prompt Library</h1>
        {isAdmin && (
          <button onClick={() => { setEditingPrompt(null); setShowForm(true) }}>
            + New Prompt
          </button>
        )}
      </div>

      <div style={{ marginBottom: '0.75rem' }}>
        {['all', 'source-list', 'papa', 'amy-bot'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              marginRight: '0.5rem',
              fontWeight: filter === f ? 'bold' : 'normal',
              textDecoration: filter === f ? 'underline' : 'none',
            }}
          >
            {f === 'all' ? 'All' : f === 'papa' ? 'Refinement (PAPA/PSST)' : f === 'source-list' ? 'Source Lists' : 'Amy Bot'}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Search prompts..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ padding: '0.4rem 0.6rem', flex: 1, maxWidth: '300px', border: '1px solid #ccc', borderRadius: '4px' }}
        />
        <select
          value={agencyFilter}
          onChange={(e) => setAgencyFilter(e.target.value)}
          style={{ padding: '0.4rem', border: '1px solid #ccc', borderRadius: '4px' }}
        >
          <option value="">All Agencies</option>
          {allAgencies.map((ag) => (
            <option key={ag} value={ag}>{ag}</option>
          ))}
        </select>
        {(searchText || agencyFilter) && (
          <button
            onClick={() => { setSearchText(''); setAgencyFilter('') }}
            style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem', cursor: 'pointer' }}
          >
            Clear
          </button>
        )}
      </div>

      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {loading && <p>Loading...</p>}

      {showForm && (
        <PromptForm
          prompt={editingPrompt}
          onSave={handleSave}
          onCancel={() => { setShowForm(false); setEditingPrompt(null) }}
        />
      )}

      {!loading && filter === 'all' && (
        <>
          <GroupedSourceLists
            prompts={sourceLists}
            isAdmin={isAdmin}
            onEdit={(p) => { setEditingPrompt(p); setShowForm(true) }}
            onDelete={handleDelete}
            selectable
            selectedPrompts={selectedPrompts}
            onToggleSelect={togglePromptSelection}
            onSelectAll={selectAllSourceLists}
            onRunSelected={handleRunSelected}
            batchRunning={batchRunning}
          />
          <PromptSection
            title="Refinement (PAPA / PSST)"
            prompts={refinement}
            isAdmin={isAdmin}
            onEdit={(p) => { setEditingPrompt(p); setShowForm(true) }}
            onDelete={handleDelete}
          />
          <PromptSection
            title="Amy Bot"
            prompts={amyBots}
            isAdmin={isAdmin}
            onEdit={(p) => { setEditingPrompt(p); setShowForm(true) }}
            onDelete={handleDelete}
          />
        </>
      )}

      {!loading && filter !== 'all' && (
        <PromptSection
          title={filter}
          prompts={filterPrompts(prompts)}
          isAdmin={isAdmin}
          onEdit={(p) => { setEditingPrompt(p); setShowForm(true) }}
          onDelete={handleDelete}
          showRouting={filter === 'source-list'}
          selectable={filter === 'source-list'}
          selectedPrompts={selectedPrompts}
          onToggleSelect={togglePromptSelection}
          onSelectAll={selectAllSourceLists}
          onRunSelected={handleRunSelected}
          batchRunning={batchRunning}
        />
      )}
    </div>
  )
}

function GroupedSourceLists({ prompts, isAdmin, onEdit, onDelete, selectable, selectedPrompts, onToggleSelect, onSelectAll, onRunSelected, batchRunning }) {
  if (prompts.length === 0) {
    return (
      <div style={{ marginBottom: '2rem' }}>
        <h2>Source Lists</h2>
        <p style={{ color: '#888' }}>No prompts yet.</p>
      </div>
    )
  }

  // Group prompts by agency → opportunity
  const grouped = {}
  for (const p of prompts) {
    const agency = p.agency || 'Ungrouped'
    const opp = p.opportunity || 'General'
    if (!grouped[agency]) grouped[agency] = {}
    if (!grouped[agency][opp]) grouped[agency][opp] = []
    grouped[agency][opp].push(p)
  }

  const agencyNames = Object.keys(grouped).sort()
  // If everything is "Ungrouped", show flat list instead
  const hasAgencies = agencyNames.length > 1 || agencyNames[0] !== 'Ungrouped'

  const selectedCount = selectable ? prompts.filter((p) => selectedPrompts && selectedPrompts.has(p.id)).length : 0
  const anyBatchRunning = batchRunning && Object.values(batchRunning).some((r) => r.status === 'running' || r.status === 'starting')

  // Build "Review All Results" link when batch runs have completed
  const completedEntries = batchRunning
    ? prompts
        .filter((p) => batchRunning[p.id]?.status === 'completed' && batchRunning[p.id]?.storyId)
        .map((p) => `${batchRunning[p.id].storyId}:${encodeURIComponent(p.name)}`)
    : []
  const allBatchDone = batchRunning && Object.keys(batchRunning).length > 0 && !anyBatchRunning
  const reviewAllUrl = completedEntries.length > 0 ? `/batch-review?stories=${completedEntries.join(',')}` : null

  return (
    <div style={{ marginBottom: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h2>Source Lists ({prompts.length})</h2>
        {selectable && (
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            {allBatchDone && reviewAllUrl && (
              <Link
                to={reviewAllUrl}
                style={{
                  padding: '0.25rem 0.75rem',
                  fontSize: '0.85rem',
                  background: '#007bff',
                  color: '#fff',
                  textDecoration: 'none',
                  borderRadius: '4px',
                  fontWeight: 'bold',
                }}
              >
                Review All Results ({completedEntries.length})
              </Link>
            )}
            <button onClick={onSelectAll} style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}>
              {selectedCount === prompts.length ? 'Deselect All' : 'Select All'}
            </button>
            {selectedCount > 0 && (
              <button
                onClick={onRunSelected}
                disabled={anyBatchRunning}
                style={{
                  padding: '0.25rem 0.75rem',
                  fontSize: '0.85rem',
                  background: anyBatchRunning ? '#6c757d' : '#28a745',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: anyBatchRunning ? 'not-allowed' : 'pointer',
                }}
              >
                {anyBatchRunning ? 'Running...' : `Run Selected (${selectedCount})`}
              </button>
            )}
          </div>
        )}
      </div>

      {hasAgencies ? (
        agencyNames.map((agency) => {
          const opportunities = Object.keys(grouped[agency]).sort()
          return (
            <div key={agency} style={{ marginBottom: '1.5rem' }}>
              <h3 style={{ margin: '0.5rem 0', color: '#333', borderBottom: '1px solid #ddd', paddingBottom: '0.25rem' }}>
                {agency}
              </h3>
              {opportunities.map((opp) => {
                const oppPrompts = grouped[agency][opp]
                return (
                  <div key={opp} style={{ marginLeft: '1rem', marginBottom: '0.75rem' }}>
                    <h4 style={{ margin: '0.25rem 0', color: '#555', fontSize: '0.95rem' }}>
                      {opp} ({oppPrompts.length} prompt{oppPrompts.length !== 1 ? 's' : ''})
                    </h4>
                    <PromptCardList
                      prompts={oppPrompts}
                      isAdmin={isAdmin}
                      onEdit={onEdit}
                      onDelete={onDelete}
                      selectable={selectable}
                      selectedPrompts={selectedPrompts}
                      onToggleSelect={onToggleSelect}
                      batchRunning={batchRunning}
                    />
                  </div>
                )
              })}
            </div>
          )
        })
      ) : (
        <PromptCardList
          prompts={prompts}
          isAdmin={isAdmin}
          onEdit={onEdit}
          onDelete={onDelete}
          selectable={selectable}
          selectedPrompts={selectedPrompts}
          onToggleSelect={onToggleSelect}
          batchRunning={batchRunning}
        />
      )}
    </div>
  )
}

function PromptCardList({ prompts, isAdmin, onEdit, onDelete, selectable, selectedPrompts, onToggleSelect, batchRunning }) {
  return (
    <div style={{ display: 'grid', gap: '0.5rem' }}>
      {prompts.map((p) => {
        const batchStatus = batchRunning && batchRunning[p.id]
        return (
          <div key={p.id} style={{
            border: batchStatus?.status === 'completed' ? '2px solid #28a745' : batchStatus?.status === 'failed' ? '2px solid #dc3545' : '1px solid #ddd',
            borderRadius: '6px',
            padding: '0.75rem 1rem',
            background: batchStatus?.status === 'running' || batchStatus?.status === 'starting' ? '#fff9e6' : undefined,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                {selectable && (
                  <input
                    type="checkbox"
                    checked={selectedPrompts && selectedPrompts.has(p.id)}
                    onChange={() => onToggleSelect(p.id)}
                    style={{ marginTop: '0.2rem' }}
                  />
                )}
                <div>
                  <strong style={{ fontSize: '0.9rem' }}>{p.name}</strong>
                  {p.description && <p style={{ color: '#666', margin: '0.15rem 0', fontSize: '0.85rem' }}>{p.description}</p>}
                  {p.opportunity && (
                    <p style={{ fontSize: '0.8rem', color: '#444', margin: '0.1rem 0' }}>
                      {p.state} | {p.pitches_per_week}/wk
                    </p>
                  )}
                  {batchStatus && (
                    <div style={{ marginTop: '0.2rem', fontSize: '0.8rem' }}>
                      {(batchStatus.status === 'starting' || batchStatus.status === 'running') && (
                        <span style={{ color: '#856404' }}>Running...</span>
                      )}
                      {batchStatus.status === 'completed' && batchStatus.storyId && (
                        <span>
                          <span style={{ color: '#155724', fontWeight: 'bold' }}>Completed</span>
                          {' '}
                          <Link to={`/batch-review?stories=${batchStatus.storyId}:${encodeURIComponent(p.name)}`} style={{ color: '#007bff' }}>View Results</Link>
                        </span>
                      )}
                      {batchStatus.status === 'completed' && !batchStatus.storyId && (
                        <span style={{ color: '#155724', fontWeight: 'bold' }}>Completed</span>
                      )}
                      {batchStatus.status === 'failed' && (
                        <span style={{ color: '#721c24' }}>Failed: {batchStatus.error}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
                <Link to={`/source-list?prompt_id=${p.id}`} style={{ padding: '0.2rem 0.6rem', background: '#007bff', color: '#fff', textDecoration: 'none', borderRadius: '4px', fontSize: '0.85rem' }}>
                  Run
                </Link>
                {isAdmin && (
                  <>
                    <button onClick={() => onEdit(p)} style={{ fontSize: '0.85rem' }}>Edit</button>
                    <button onClick={() => onDelete(p.id)} style={{ color: 'red', fontSize: '0.85rem' }}>Delete</button>
                  </>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function PromptSection({ title, prompts, isAdmin, onEdit, onDelete, showRouting, selectable, selectedPrompts, onToggleSelect, onSelectAll, onRunSelected, batchRunning }) {
  if (prompts.length === 0) {
    return (
      <div style={{ marginBottom: '2rem' }}>
        <h2>{title}</h2>
        <p style={{ color: '#888' }}>No prompts yet.</p>
      </div>
    )
  }

  const selectedCount = selectable ? prompts.filter((p) => selectedPrompts && selectedPrompts.has(p.id)).length : 0
  const anyBatchRunning = batchRunning && Object.values(batchRunning).some((r) => r.status === 'running' || r.status === 'starting')

  const completedEntries = batchRunning
    ? prompts
        .filter((p) => batchRunning[p.id]?.status === 'completed' && batchRunning[p.id]?.storyId)
        .map((p) => `${batchRunning[p.id].storyId}:${encodeURIComponent(p.name)}`)
    : []
  const allBatchDone = batchRunning && Object.keys(batchRunning).length > 0 && !anyBatchRunning
  const reviewAllUrl = completedEntries.length > 0 ? `/batch-review?stories=${completedEntries.join(',')}` : null

  return (
    <div style={{ marginBottom: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h2>{title} ({prompts.length})</h2>
        {selectable && (
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            {allBatchDone && reviewAllUrl && (
              <Link
                to={reviewAllUrl}
                style={{
                  padding: '0.25rem 0.75rem',
                  fontSize: '0.85rem',
                  background: '#007bff',
                  color: '#fff',
                  textDecoration: 'none',
                  borderRadius: '4px',
                  fontWeight: 'bold',
                }}
              >
                Review All Results ({completedEntries.length})
              </Link>
            )}
            <button
              onClick={onSelectAll}
              style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}
            >
              {selectedCount === prompts.length ? 'Deselect All' : 'Select All'}
            </button>
            {selectedCount > 0 && (
              <button
                onClick={onRunSelected}
                disabled={anyBatchRunning}
                style={{
                  padding: '0.25rem 0.75rem',
                  fontSize: '0.85rem',
                  background: anyBatchRunning ? '#6c757d' : '#28a745',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: anyBatchRunning ? 'not-allowed' : 'pointer',
                }}
              >
                {anyBatchRunning ? 'Running...' : `Run Selected (${selectedCount})`}
              </button>
            )}
          </div>
        )}
      </div>
      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {prompts.map((p) => {
          const batchStatus = batchRunning && batchRunning[p.id]
          return (
            <div key={p.id} style={{
              border: batchStatus?.status === 'completed' ? '2px solid #28a745' : batchStatus?.status === 'failed' ? '2px solid #dc3545' : '1px solid #ddd',
              borderRadius: '6px',
              padding: '1rem',
              background: batchStatus?.status === 'running' || batchStatus?.status === 'starting' ? '#fff9e6' : undefined,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                  {selectable && (
                    <input
                      type="checkbox"
                      checked={selectedPrompts && selectedPrompts.has(p.id)}
                      onChange={() => onToggleSelect(p.id)}
                      style={{ marginTop: '0.25rem' }}
                    />
                  )}
                  <div>
                    <strong>{p.name}</strong>
                    {p.description && <p style={{ color: '#666', margin: '0.25rem 0', fontSize: '0.9rem' }}>{p.description}</p>}
                    {showRouting && p.opportunity && (
                      <p style={{ fontSize: '0.85rem', color: '#444' }}>
                        {p.opportunity} | {p.state} | {p.pitches_per_week}/wk
                      </p>
                    )}
                    {batchStatus && (
                      <div style={{ marginTop: '0.25rem', fontSize: '0.85rem' }}>
                        {(batchStatus.status === 'starting' || batchStatus.status === 'running') && (
                          <span style={{ color: '#856404' }}>Running...</span>
                        )}
                        {batchStatus.status === 'completed' && batchStatus.storyId && (
                          <span>
                            <span style={{ color: '#155724', fontWeight: 'bold' }}>Completed</span>
                            {' '}
                            <Link to={`/batch-review?stories=${batchStatus.storyId}:${encodeURIComponent(p.name)}`} style={{ color: '#007bff' }}>View Results</Link>
                          </span>
                        )}
                        {batchStatus.status === 'completed' && !batchStatus.storyId && (
                          <span style={{ color: '#155724', fontWeight: 'bold' }}>Completed</span>
                        )}
                        {batchStatus.status === 'failed' && (
                          <span style={{ color: '#721c24' }}>Failed: {batchStatus.error}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
                  {showRouting && (
                    <Link to={`/source-list?prompt_id=${p.id}`} style={{ padding: '0.25rem 0.75rem', background: '#007bff', color: '#fff', textDecoration: 'none', borderRadius: '4px', fontSize: '0.9rem' }}>
                      Run
                    </Link>
                  )}
                  {isAdmin && (
                    <>
                      <button onClick={() => onEdit(p)}>Edit</button>
                      <button onClick={() => onDelete(p.id)} style={{ color: 'red' }}>Delete</button>
                    </>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function PromptForm({ prompt, onSave, onCancel }) {
  const [formData, setFormData] = useState({
    prompt_type: prompt?.prompt_type || 'papa',
    name: prompt?.name || '',
    prompt_text: prompt?.prompt_text || '',
    description: prompt?.description || '',
    agency: prompt?.agency || '',
    issuer: prompt?.issuer || '',
    opportunity: prompt?.opportunity || '',
    state: prompt?.state || '',
    publications: prompt?.publications || '',
    topic_summary: prompt?.topic_summary || '',
    context: prompt?.context || '',
    pitches_per_week: prompt?.pitches_per_week || '',
  })

  function handleChange(e) {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  function handleSubmit(e) {
    e.preventDefault()
    const data = { ...formData }
    if (data.pitches_per_week) data.pitches_per_week = parseInt(data.pitches_per_week, 10)
    onSave(data)
  }

  const isSourceList = formData.prompt_type === 'source-list'

  return (
    <form onSubmit={handleSubmit} style={{ border: '2px solid #007bff', borderRadius: '8px', padding: '1.5rem', marginBottom: '1.5rem', background: '#f9f9f9' }}>
      <h3>{prompt ? 'Edit Prompt' : 'New Prompt'}</h3>

      <div style={{ marginBottom: '0.75rem' }}>
        <label>Type: </label>
        <select name="prompt_type" value={formData.prompt_type} onChange={handleChange} disabled={!!prompt}>
          <option value="source-list">Source List</option>
          <option value="papa">Refinement (PAPA/PSST)</option>
          <option value="amy-bot">Amy Bot</option>
        </select>
      </div>

      <div style={{ marginBottom: '0.75rem' }}>
        <label>Name: </label>
        <input name="name" value={formData.name} onChange={handleChange} required style={{ width: '100%' }} />
      </div>

      <div style={{ marginBottom: '0.75rem' }}>
        <label>Description: </label>
        <input name="description" value={formData.description} onChange={handleChange} style={{ width: '100%' }} />
      </div>

      <div style={{ marginBottom: '0.75rem' }}>
        <label>Agency: </label>
        <input name="agency" value={formData.agency} onChange={handleChange} placeholder="e.g. US Regional News Network - Baseline" style={{ width: '100%' }} />
      </div>

      <div style={{ marginBottom: '0.75rem' }}>
        <label>Prompt Text: </label>
        <textarea name="prompt_text" value={formData.prompt_text} onChange={handleChange} required rows={8} style={{ width: '100%' }} />
      </div>

      {isSourceList && (
        <>
          <h4>Routing Metadata</h4>
          {['issuer', 'opportunity', 'state', 'publications'].map((field) => (
            <div key={field} style={{ marginBottom: '0.5rem' }}>
              <label>{field}: </label>
              <input name={field} value={formData[field]} onChange={handleChange} style={{ width: '100%' }} />
            </div>
          ))}
          <div style={{ marginBottom: '0.5rem' }}>
            <label>Topic Summary: </label>
            <textarea name="topic_summary" value={formData.topic_summary} onChange={handleChange} rows={3} style={{ width: '100%' }} />
          </div>
          <div style={{ marginBottom: '0.5rem' }}>
            <label>Context: </label>
            <textarea name="context" value={formData.context} onChange={handleChange} rows={3} style={{ width: '100%' }} />
          </div>
          <div style={{ marginBottom: '0.5rem' }}>
            <label>Pitches/Week: </label>
            <input name="pitches_per_week" type="number" value={formData.pitches_per_week} onChange={handleChange} />
          </div>
        </>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <button type="submit">{prompt ? 'Update' : 'Create'}</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

export default PromptLibraryPage
