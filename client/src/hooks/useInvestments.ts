import { useQuery } from '@tanstack/react-query'
import { listHoldings, getPortfolioSummary, listSips, listFds } from '@/api/investments'
import { useAuthStore } from '@/store/auth'

function enabled() {
  return useAuthStore.getState().isAuthenticated
}

export function useHoldings() {
  return useQuery({
    queryKey: ['investments', 'holdings'],
    queryFn: listHoldings,
    enabled: enabled(),
  })
}

export function usePortfolioSummary() {
  return useQuery({
    queryKey: ['investments', 'summary'],
    queryFn: getPortfolioSummary,
    enabled: enabled(),
  })
}

export function useSips() {
  return useQuery({
    queryKey: ['investments', 'sips'],
    queryFn: listSips,
    enabled: enabled(),
  })
}

export function useFds() {
  return useQuery({
    queryKey: ['investments', 'fds'],
    queryFn: listFds,
    enabled: enabled(),
  })
}
