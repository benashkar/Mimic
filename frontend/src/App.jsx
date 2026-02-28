import { Routes, Route, Link } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { AuthProvider, useAuth } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import PromptLibraryPage from './pages/PromptLibraryPage'
import SourceListRunPage from './pages/SourceListRunPage'
import PipelinePage from './pages/PipelinePage'
import StoriesPage from './pages/StoriesPage'
import BatchResultsPage from './pages/BatchResultsPage'
import AdminUsersPage from './pages/AdminUsersPage'

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
        {user.role === 'admin' && (
          <Link to="/admin/users" style={{ marginRight: '1rem' }}>Users</Link>
        )}
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
            <Route path="/prompts" element={<ProtectedRoute><PromptLibraryPage /></ProtectedRoute>} />
            <Route path="/source-list" element={<ProtectedRoute><SourceListRunPage /></ProtectedRoute>} />
            <Route path="/pipeline" element={<ProtectedRoute><PipelinePage /></ProtectedRoute>} />
            <Route path="/stories" element={<ProtectedRoute><StoriesPage /></ProtectedRoute>} />
            <Route path="/batch-results" element={<ProtectedRoute><BatchResultsPage /></ProtectedRoute>} />
            <Route path="/admin/users" element={<ProtectedRoute><AdminUsersPage /></ProtectedRoute>} />
          </Routes>
        </main>
      </AuthProvider>
    </GoogleOAuthProvider>
  )
}

export default App
