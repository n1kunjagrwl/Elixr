import { useQuery } from '@tanstack/react-query'
import { listCategories } from '@/api/categories'
import { useAuthStore } from '@/store/auth'

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: listCategories,
    enabled: useAuthStore.getState().isAuthenticated,
    staleTime: 5 * 60_000,
  })
}
