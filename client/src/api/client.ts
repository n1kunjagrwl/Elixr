import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

let accessToken: string | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    const axiosError = error as {
      response?: { status: number }
      config: { _retry?: boolean; url?: string; headers: Record<string, string> }
    }
    const original = axiosError.config
    const isRefreshEndpoint = original.url?.includes('/auth/refresh')
    if (axiosError.response?.status === 401 && !original._retry && !isRefreshEndpoint) {
      original._retry = true
      try {
        const { data } = await axios.post<{ access_token: string }>(
          '/api/v1/auth/refresh',
          {},
          { withCredentials: true }
        )
        setAccessToken(data.access_token)
        original.headers.Authorization = `Bearer ${data.access_token}`
        // Notify auth store of the new token without importing it (avoids circular dep)
        window.dispatchEvent(new CustomEvent('elixir:token:refreshed', { detail: data.access_token }))
        return api(original)
      } catch {
        setAccessToken(null)
        window.dispatchEvent(new CustomEvent('elixir:auth:expired'))
      }
    }
    return Promise.reject(error)
  }
)

export default api
