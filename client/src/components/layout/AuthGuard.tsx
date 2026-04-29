import { useEffect } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { refreshSession } from '@/api/identity'

export function AuthGuard() {
  const { isAuthenticated, isBootstrapping, setToken, setBootstrapping } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    // Skip network round-trip when the user just logged in (token already in memory).
    if (useAuthStore.getState().isAuthenticated) {
      setBootstrapping(false)
      return
    }
    refreshSession()
      .then(({ access_token }) => {
        setToken(access_token)
      })
      .catch(() => {
        setToken(null)
        navigate('/login', { replace: true })
      })
      .finally(() => {
        setBootstrapping(false)
      })
    // Only runs on mount — bootstraps auth state from httpOnly refresh cookie.
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (isBootstrapping) {
    return (
      <div className="flex h-dvh items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!isAuthenticated) return null

  return <Outlet />
}
