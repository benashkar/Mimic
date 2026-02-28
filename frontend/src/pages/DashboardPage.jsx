import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiClient } from '../api/client'

function DashboardPage() {
  const { user } = useAuth()
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiClient('/health')
      .then((data) => setHealth(data))
      .catch((err) => setError(err.message))

    apiClient('/stories/stats')
      .then((data) => setStats(data))
      .catch(() => {})
  }, [])

  return (
    <div>
      <h1>Mimic Dashboard</h1>
      {user && (
        <p style={{ color: '#555' }}>
          Logged in as <strong>{user.display_name || user.email}</strong> ({user.role})
        </p>
      )}

      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
          <StatCard label="Total Stories" value={stats.total} />
          <StatCard label="Approved" value={stats.approved} color="#28a745" />
          <StatCard label="Rejected" value={stats.rejected} color="#dc3545" />
          <StatCard label="Approval Rate" value={`${stats.approval_rate}%`} color="#007bff" />
        </div>
      )}

      {stats && stats.by_opportunity && stats.by_opportunity.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          <h2>By Opportunity</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
                <th style={{ padding: '0.5rem' }}>Opportunity</th>
                <th style={{ padding: '0.5rem' }}>Total</th>
                <th style={{ padding: '0.5rem' }}>Approved</th>
              </tr>
            </thead>
            <tbody>
              {stats.by_opportunity.map((opp) => (
                <tr key={opp.name} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '0.5rem' }}>{opp.name}</td>
                  <td style={{ padding: '0.5rem' }}>{opp.total}</td>
                  <td style={{ padding: '0.5rem' }}>{opp.approved}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
        <Link to="/prompts" style={{ padding: '0.75rem 1.5rem', background: '#007bff', color: '#fff', textDecoration: 'none', borderRadius: '4px' }}>
          Prompt Library
        </Link>
        <Link to="/stories" style={{ padding: '0.75rem 1.5rem', background: '#6c757d', color: '#fff', textDecoration: 'none', borderRadius: '4px' }}>
          View Stories
        </Link>
      </div>

      <h2>API Health</h2>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {health ? (
        <pre style={{ background: '#f4f4f4', padding: '1rem', borderRadius: '4px' }}>
          {JSON.stringify(health, null, 2)}
        </pre>
      ) : (
        !error && <p>Loading...</p>
      )}
    </div>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '1rem', textAlign: 'center' }}>
      <div style={{ fontSize: '2rem', fontWeight: 'bold', color: color || '#333' }}>{value}</div>
      <div style={{ color: '#666', fontSize: '0.9rem' }}>{label}</div>
    </div>
  )
}

export default DashboardPage
