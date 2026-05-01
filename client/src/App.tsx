import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PageShell } from '@/components/layout/PageShell'
import { AuthGuard } from '@/components/layout/AuthGuard'
import { ErrorBoundary } from '@/components/layout/ErrorBoundary'
import { useAuthStore } from '@/store/auth'

const LoginPage = lazy(() => import('@/pages/auth/LoginPage'))
const HomePage = lazy(() => import('@/pages/home/HomePage'))
const TransactionsPage = lazy(() => import('@/pages/transactions/TransactionsPage'))
const InvestmentsPage = lazy(() => import('@/pages/investments/InvestmentsPage'))
const PeersPage = lazy(() => import('@/pages/peers/PeersPage'))
const MorePage = lazy(() => import('@/pages/more/MorePage'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

function PageFallback() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  )
}

// Listens for auth events dispatched by the Axios interceptor (avoids circular imports).
function AuthEventListener() {
  const { setToken } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    function onExpired() {
      setToken(null)
      navigate('/login', { replace: true })
    }
    function onRefreshed(e: Event) {
      const token = (e as CustomEvent<string>).detail
      setToken(token)
    }
    window.addEventListener('elixir:auth:expired', onExpired)
    window.addEventListener('elixir:token:refreshed', onRefreshed)
    return () => {
      window.removeEventListener('elixir:auth:expired', onExpired)
      window.removeEventListener('elixir:token:refreshed', onRefreshed)
    }
  }, [navigate, setToken])

  return null
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthEventListener />
        <Routes>
          <Route
            path="/login"
            element={
              <ErrorBoundary>
                <Suspense fallback={<PageFallback />}>
                  <LoginPage />
                </Suspense>
              </ErrorBoundary>
            }
          />

          {/* Protected tab routes */}
          <Route element={<AuthGuard />}>
            <Route element={<PageShell />}>
              <Route index element={<Navigate to="/home" replace />} />
              <Route
                path="/home"
                element={<ErrorBoundary><Suspense fallback={<PageFallback />}><HomePage /></Suspense></ErrorBoundary>}
              />
              <Route
                path="/transactions"
                element={<ErrorBoundary><Suspense fallback={<PageFallback />}><TransactionsPage /></Suspense></ErrorBoundary>}
              />
              <Route
                path="/investments"
                element={<ErrorBoundary><Suspense fallback={<PageFallback />}><InvestmentsPage /></Suspense></ErrorBoundary>}
              />
              <Route
                path="/peers"
                element={<ErrorBoundary><Suspense fallback={<PageFallback />}><PeersPage /></Suspense></ErrorBoundary>}
              />
              <Route
                path="/more"
                element={<ErrorBoundary><Suspense fallback={<PageFallback />}><MorePage /></Suspense></ErrorBoundary>}
              />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
