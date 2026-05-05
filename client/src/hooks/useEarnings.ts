import { useQuery } from '@tanstack/react-query'
import { listEarnings, listEarningSources } from '@/api/earnings'
import { useAuthStore } from '@/store/auth'

export function useEarnings() {
  return useQuery({
    queryKey: ['earnings'],
    queryFn: listEarnings,
    enabled: useAuthStore.getState().isAuthenticated,
  })
}

export function useEarningSources() {
  return useQuery({
    queryKey: ['earnings', 'sources'],
    queryFn: listEarningSources,
    enabled: useAuthStore.getState().isAuthenticated,
    staleTime: 5 * 60_000,
  })
}
