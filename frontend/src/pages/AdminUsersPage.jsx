import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { apiClient } from '../api/client'

function AdminUsersPage() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState([])
  const [agencies, setAgencies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingUser, setEditingUser] = useState(null)
  const [showInvite, setShowInvite] = useState(false)

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

  async function handleRoleChange(userId, newRole) {
    try {
      await apiClient(`/admin/users/${userId}/role`, {
        method: 'PUT',
        body: JSON.stringify({ role: newRole }),
      })
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <p>Loading...</p>
  if (error) return <p style={{ color: 'red' }}>Error: {error}</p>

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1 style={{ margin: 0 }}>User Management</h1>
        <button
          onClick={() => setShowInvite(true)}
          style={{ background: '#007bff', color: '#fff', border: 'none', borderRadius: '4px', padding: '0.5rem 1rem', cursor: 'pointer', fontSize: '0.9rem' }}
        >
          + Invite User
        </button>
      </div>
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
                  {!u.google_id && (
                    <span style={{
                      display: 'inline-block',
                      padding: '0.1rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.7rem',
                      fontWeight: 'bold',
                      color: '#856404',
                      background: '#fff3cd',
                    }}>
                      INVITED
                    </span>
                  )}
                  {currentUser && currentUser.id !== u.id ? (
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      style={{
                        padding: '0.1rem 0.3rem',
                        borderRadius: '3px',
                        fontSize: '0.75rem',
                        fontWeight: 'bold',
                        color: '#fff',
                        background: u.role === 'admin' ? '#dc3545' : '#6c757d',
                        border: 'none',
                        cursor: 'pointer',
                      }}
                    >
                      <option value="user">user</option>
                      <option value="admin">admin</option>
                    </select>
                  ) : (
                    <span style={{
                      display: 'inline-block',
                      padding: '0.1rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.75rem',
                      fontWeight: 'bold',
                      color: '#fff',
                      background: u.role === 'admin' ? '#dc3545' : '#6c757d',
                    }}>
                      {u.role} (you)
                    </span>
                  )}
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
              <button
                onClick={() => setEditingUser(u)}
                style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}
              >
                Edit Access
              </button>
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

      {showInvite && (
        <InviteModal
          onInvite={async (email, role) => {
            await apiClient('/admin/users/invite', {
              method: 'POST',
              body: JSON.stringify({ email, role }),
            })
            setShowInvite(false)
            loadData()
          }}
          onCancel={() => setShowInvite(false)}
        />
      )}
    </div>
  )
}

function InviteModal({ onInvite, onCancel }) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('user')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onInvite(email.trim(), role)
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
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
        width: '400px',
      }}>
        <h3>Invite User</h3>
        <p style={{ color: '#666', fontSize: '0.85rem', marginBottom: '1rem' }}>
          Pre-create a user account. When they log in via Google, they will get the role and agencies you assign.
        </p>

        {error && <p style={{ color: 'red', fontSize: '0.85rem' }}>{error}</p>}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '0.75rem' }}>
            <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem', fontSize: '0.85rem' }}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="user@example.com"
              style={{ width: '100%', padding: '0.4rem', boxSizing: 'border-box' }}
            />
          </div>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem', fontSize: '0.85rem' }}>Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              style={{ width: '100%', padding: '0.4rem' }}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button type="button" onClick={onCancel}>Cancel</button>
            <button
              type="submit"
              disabled={saving}
              style={{ background: '#007bff', color: '#fff', border: 'none', borderRadius: '4px', padding: '0.4rem 1rem', cursor: 'pointer' }}
            >
              {saving ? 'Inviting...' : 'Invite'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function AgencyEditor({ user, availableAgencies, onSave, onCancel }) {
  const [assignments, setAssignments] = useState(
    user.agencies.map((ua) => ({
      agency: ua.agency,
      opportunity: ua.opportunity || '__all__',
    }))
  )
  const [saving, setSaving] = useState(false)

  function addRow() {
    setAssignments([...assignments, { agency: '', opportunity: '' }])
  }

  function removeRow(index) {
    setAssignments(assignments.filter((_, i) => i !== index))
  }

  function updateRow(index, field, value) {
    const updated = assignments.map((a, i) => {
      if (i !== index) return a
      if (field === 'agency') {
        // Reset opportunity when agency changes
        return { ...a, agency: value, opportunity: '' }
      }
      return { ...a, [field]: value }
    })
    setAssignments(updated)
  }

  function getOpportunities(agencyName) {
    const entry = availableAgencies.find((a) => a.agency === agencyName)
    return entry ? entry.opportunities : []
  }

  async function handleSave() {
    setSaving(true)
    const cleaned = assignments
      .filter((a) => a.agency && a.opportunity)
      .map((a) => ({
        agency: a.agency,
        opportunity: a.opportunity === '__all__' ? null : a.opportunity,
      }))
    await onSave(cleaned)
    setSaving(false)
  }

  const allValid = assignments.every((a) => a.agency && a.opportunity)

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
        width: '550px',
        maxHeight: '80vh',
        overflow: 'auto',
      }}>
        <h3>Edit Access: {user.display_name || user.email}</h3>
        <p style={{ color: '#666', fontSize: '0.85rem', marginBottom: '1rem' }}>
          Select an agency and choose &quot;All Opportunities&quot; or a specific one.
        </p>

        {assignments.map((a, i) => {
          const opps = getOpportunities(a.agency)
          return (
            <div key={i} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'center' }}>
              <select
                value={a.agency}
                onChange={(e) => updateRow(i, 'agency', e.target.value)}
                style={{ flex: 1, padding: '0.35rem' }}
              >
                <option value="">Select agency...</option>
                {availableAgencies.map((ag) => (
                  <option key={ag.agency} value={ag.agency}>{ag.agency}</option>
                ))}
              </select>
              <select
                value={a.opportunity}
                onChange={(e) => updateRow(i, 'opportunity', e.target.value)}
                style={{ flex: 1, padding: '0.35rem' }}
                disabled={!a.agency}
              >
                <option value="">Select opportunity...</option>
                {a.agency && <option value="__all__">All Opportunities</option>}
                {opps.map((opp) => (
                  <option key={opp} value={opp}>{opp}</option>
                ))}
              </select>
              <button
                onClick={() => removeRow(i)}
                style={{ color: 'red', border: 'none', background: 'none', cursor: 'pointer', fontSize: '1.1rem' }}
              >
                x
              </button>
            </div>
          )
        })}

        <button onClick={addRow} style={{ marginBottom: '1rem', fontSize: '0.85rem' }}>
          + Add Agency
        </button>

        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button onClick={onCancel}>Cancel</button>
          <button
            onClick={handleSave}
            disabled={saving || !allValid}
            style={{
              background: saving || !allValid ? '#6c757d' : '#28a745',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              padding: '0.4rem 1rem',
              cursor: saving || !allValid ? 'not-allowed' : 'pointer',
            }}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default AdminUsersPage
