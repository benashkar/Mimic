import { useState, useEffect } from 'react'

function DashboardPage() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div>
      <h1>Mimic Dashboard</h1>
      <h2>API Health Check</h2>
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

export default DashboardPage
