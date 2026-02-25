/**
 * Authenticated fetch wrapper.
 *
 * Attaches JWT from localStorage to every request.
 * Returns parsed JSON or throws on non-OK responses.
 */

const API_BASE = '/api'

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

  const data = await resp.json().catch(() => null)

  if (!resp.ok) {
    const message = (data && data.error) || resp.statusText
    const err = new Error(message)
    err.status = resp.status
    throw err
  }

  return data
}
