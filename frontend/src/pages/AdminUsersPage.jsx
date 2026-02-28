import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'

function AdminUsersPage() {
  const [users, setUsers] = useState([])
  const [agencies, setAgencies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingUser, setEditingUser] = useState(null)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      const [usersData, agenciesData] = await Promise.all([
        apiClient('/admin/users'),
        apiClient('/admin/agencies'),
      ])
      setUsers(usersData)
      setAgencies(agenciesData)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <p>Loading...</p>
  if (error) return <p style={{ color: 'red' }}>Error: {error}</p>

  return (
    <div>
      <h1>User Management</h1>
      <p style={{ color: '#666', marginBottom: '1rem' }}>
        Assign agencies and opportunities to control which prompts each user can see.
        Admins always see everything.
      </p>

      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {users.map((u) => (
          <div
            key={u.id}
            style={{
              border: '1px solid #ddd',
              borderRadius: '6px',
              padding: '1rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <strong>{u.display_name || u.email}</strong>
                  <span style={{
                    display: 'inline-block',
                    padding: '0.1rem 0.4rem',
                    borderRadius: '3px',
                    fontSize: '0.75rem',
                    fontWeight: 'bold',
                    color: '#fff',
                    background: u.role === 'admin' ? '#dc3545' : '#6c757d',
                  }}>
                    {u.role}
                  </span>
                </div>
                <p style={{ margin: '0.25rem 0', fontSize: '0.85rem', color: '#666' }}>{u.email}</p>
                {u.agencies && u.agencies.length > 0 ? (
                  <div style={{ marginTop: '0.25rem' }}>
                    {u.agencies.map((ua) => (
                      <span
                        key={ua.id}
                        style={{
                          display: 'inline-block',
                          padding: '0.15rem 0.5rem',
                          margin: '0.15rem 0.25rem 0.15rem 0',
                          borderRadius: '3px',
                          fontSize: '0.8rem',
                          background: '#e9ecef',
                          color: '#333',
                        }}
                      >
                        {ua.agency}{ua.opportunity ? ` / ${ua.opportunity}` : ' (all)'}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p style={{ margin: '0.25rem 0', fontSize: '0.85rem', color: '#999' }}>
                    {u.role === 'admin' ? 'Admin — sees everything' : 'No agencies assigned'}
                  </p>
                )}
              </div>
              {u.role !== 'admin' && (
                <button
                  onClick={() => setEditingUser(u)}
                  style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}
                >
                  Edit Access
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {editingUser && (
        <AgencyEditor
          user={editingUser}
          availableAgencies={agencies}
          onSave={async (assignments) => {
            try {
              await apiClient(`/admin/users/${editingUser.id}/agencies`, {
                method: 'PUT',
                body: JSON.stringify({ agencies: assignments }),
              })
              setEditingUser(null)
              loadData()
            } catch (err) {
              setError(err.message)
            }
          }}
          onCancel={() => setEditingUser(null)}
        />
      )}
    </div>
  )
}

function AgencyEditor({ user, availableAgencies, onSave, onCancel }) {
  const [assignments, setAssignments] = useState(
    user.agencies.map((ua) => ({ agency: ua.agency, opportunity: ua.opportunity || '' }))
  )
  const [saving, setSaving] = useState(false)

  function addRow() {
    setAssignments([...assignments, { agency: '', opportunity: '' }])
  }

  function removeRow(index) {
    setAssignments(assignments.filter((_, i) => i !== index))
  }

  function updateRow(index, field, value) {
    setAssignments(assignments.map((a, i) => i === index ? { ...a, [field]: value } : a))
  }

  async function handleSave() {
    setSaving(true)
    const cleaned = assignments
      .filter((a) => a.agency.trim())
      .map((a) => ({
        agency: a.agency.trim(),
        opportunity: a.opportunity.trim() || null,
      }))
    await onSave(cleaned)
    setSaving(false)
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    }}>
      <div style={{
        background: '#fff',
        borderRadius: '8px',
        padding: '1.5rem',
        width: '500px',
        maxHeight: '80vh',
        overflow: 'auto',
      }}>
        <h3>Edit Access: {user.display_name || user.email}</h3>
        <p style={{ color: '#666', fontSize: '0.85rem', marginBottom: '1rem' }}>
          Leave opportunity blank to grant access to all opportunities under an agency.
        </p>

        {assignments.map((a, i) => (
          <div key={i} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'center' }}>
            <select
              value={a.agency}
              onChange={(e) => updateRow(i, 'agency', e.target.value)}
              style={{ flex: 2, padding: '0.35rem' }}
            >
              <option value="">Select agency...</option>
              {availableAgencies.map((ag) => (
                <option key={ag} value={ag}>{ag}</option>
              ))}
            </select>
            <input
              placeholder="Opportunity (optional)"
              value={a.opportunity}
              onChange={(e) => updateRow(i, 'opportunity', e.target.value)}
              style={{ flex: 1, padding: '0.35rem' }}
            />
            <button
              onClick={() => removeRow(i)}
              style={{ color: 'red', border: 'none', background: 'none', cursor: 'pointer', fontSize: '1.1rem' }}
            >
              x
            </button>
          </div>
        ))}

        <button onClick={addRow} style={{ marginBottom: '1rem', fontSize: '0.85rem' }}>
          + Add Agency
        </button>

        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button onClick={onCancel}>Cancel</button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{ background: '#28a745', color: '#fff', border: 'none', borderRadius: '4px', padding: '0.4rem 1rem', cursor: 'pointer' }}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default AdminUsersPage
