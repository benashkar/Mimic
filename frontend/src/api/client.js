/**
 * Authenticated fetch wrapper.
 *
 * Attaches JWT from localStorage to every request.
 * Returns parsed JSON or throws on non-OK responses.
 */

const API_BASE = import.meta.env.VITE_API_URL || '/api'

export async function apiClient(path, options = {}) {
  const token = localStorage.getItem('mimic_token')
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  let data = null
  const text = await resp.text()
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    // Response body is not valid JSON
  }

  if (!resp.ok) {
    const message = (data && data.error) || resp.statusText || `HTTP ${resp.status}`
    const err = new Error(message)
    err.status = resp.status
    throw err
  }

  if (data === null) {
    throw new Error(`Server returned ${resp.status} with no JSON body`)
  }

  return data
}
