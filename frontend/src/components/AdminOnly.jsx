import { useAuth } from '../context/AuthContext'

function AdminOnly({ children }) {
  const { user } = useAuth()

  if (!user || user.role !== 'admin') {
    return null
  }

  return children
}

export default AdminOnly
