import { createContext, useContext, useState, useEffect } from 'react'
import { apiClient } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => localStorage.getItem('mimic_token'))
  const [loading, setLoading] = useState(!!localStorage.getItem('mimic_token'))

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }

    apiClient('/auth/me')
      .then((data) => setUser(data))
      .catch(() => {
        localStorage.removeItem('mimic_token')
        setToken(null)
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [token])

  async function login(googleCredential) {
    const data = await apiClient('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ token: googleCredential }),
    })
    localStorage.setItem('mimic_token', data.token)
    setToken(data.token)
    setUser(data.user)
  }

  function logout() {
    apiClient('/auth/logout', { method: 'POST' }).catch(() => {})
    localStorage.removeItem('mimic_token')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
