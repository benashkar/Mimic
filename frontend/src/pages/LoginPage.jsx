import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import GoogleLoginBtn from '../components/GoogleLoginBtn'

function LoginPage() {
  const { user, loading } = useAuth()

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading...</div>
  }

  if (user) {
    return <Navigate to="/" replace />
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
    }}>
      <div style={{
        border: '1px solid #ccc',
        borderRadius: '8px',
        padding: '2rem',
        textAlign: 'center',
        maxWidth: '400px',
        width: '100%',
      }}>
        <h1>Tor-Bot</h1>
        <p style={{ color: '#666', marginBottom: '1.5rem' }}>
          Sign in to continue
        </p>
        <GoogleLoginBtn />
      </div>
    </div>
  )
}

export default LoginPage
