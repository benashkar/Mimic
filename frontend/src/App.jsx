import { Routes, Route, Link } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { AuthProvider, useAuth } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

function AppNav() {
  const { user, logout } = useAuth()

  if (!user) return null

  return (
    <nav style={{ padding: '1rem', borderBottom: '1px solid #ccc', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div>
        <Link to="/" style={{ marginRight: '1rem' }}>Dashboard</Link>
        <Link to="/prompts" style={{ marginRight: '1rem' }}>Prompts</Link>
        <Link to="/stories" style={{ marginRight: '1rem' }}>Stories</Link>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <span style={{ fontSize: '0.9rem', color: '#555' }}>{user.email}</span>
        <button onClick={logout} style={{ cursor: 'pointer' }}>Logout</button>
      </div>
    </nav>
  )
}

function App() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <AuthProvider>
        <AppNav />
        <main style={{ padding: '1rem' }}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
            <Route path="/prompts" element={<ProtectedRoute><div><h1>Prompt Library</h1><p>Coming in Phase 3.</p></div></ProtectedRoute>} />
            <Route path="/stories" element={<ProtectedRoute><div><h1>Stories</h1><p>Coming in Phase 6.</p></div></ProtectedRoute>} />
          </Routes>
        </main>
      </AuthProvider>
    </GoogleOAuthProvider>
  )
}

export default App
