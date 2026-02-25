import { GoogleLogin } from '@react-oauth/google'
import { useAuth } from '../context/AuthContext'

function GoogleLoginBtn() {
  const { login } = useAuth()

  return (
    <GoogleLogin
      onSuccess={(credentialResponse) => {
        login(credentialResponse.credential)
      }}
      onError={() => {
        console.error('Google login failed')
      }}
    />
  )
}

export default GoogleLoginBtn
