import { useQuery } from '@tanstack/react-query'
import { listAccounts } from '@/api/accounts'
import { useAuthStore } from '@/store/auth'

export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: listAccounts,
    enabled: useAuthStore.getState().isAuthenticated,
    staleTime: 5 * 60_000,
  })
}
