import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiClient } from '../api/client'

function PromptLibraryPage() {
  const { user } = useAuth()
  const [prompts, setPrompts] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editingPrompt, setEditingPrompt] = useState(null)

  const isAdmin = user && user.role === 'admin'

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

  const sourceLists = prompts.filter((p) => p.prompt_type === 'source-list')
  const refinement = prompts.filter((p) => p.prompt_type === 'papa')
  const amyBots = prompts.filter((p) => p.prompt_type === 'amy-bot')

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

      <div style={{ marginBottom: '1rem' }}>
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
          <PromptSection
            title="Source Lists"
            prompts={sourceLists}
            isAdmin={isAdmin}
            onEdit={(p) => { setEditingPrompt(p); setShowForm(true) }}
            onDelete={handleDelete}
            showRouting
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
          prompts={prompts}
          isAdmin={isAdmin}
          onEdit={(p) => { setEditingPrompt(p); setShowForm(true) }}
          onDelete={handleDelete}
          showRouting={filter === 'source-list'}
        />
      )}
    </div>
  )
}

function PromptSection({ title, prompts, isAdmin, onEdit, onDelete, showRouting }) {
  if (prompts.length === 0) {
    return (
      <div style={{ marginBottom: '2rem' }}>
        <h2>{title}</h2>
        <p style={{ color: '#888' }}>No prompts yet.</p>
      </div>
    )
  }

  return (
    <div style={{ marginBottom: '2rem' }}>
      <h2>{title} ({prompts.length})</h2>
      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {prompts.map((p) => (
          <div key={p.id} style={{ border: '1px solid #ddd', borderRadius: '6px', padding: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <strong>{p.name}</strong>
                {p.description && <p style={{ color: '#666', margin: '0.25rem 0', fontSize: '0.9rem' }}>{p.description}</p>}
                {showRouting && p.opportunity && (
                  <p style={{ fontSize: '0.85rem', color: '#444' }}>
                    {p.opportunity} | {p.state} | {p.pitches_per_week}/wk
                  </p>
                )}
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
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
        ))}
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
