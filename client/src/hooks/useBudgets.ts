import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listBudgets, createBudget, deleteBudget } from '@/api/budgets'
import { useAuthStore } from '@/store/auth'

export function useBudgets() {
  return useQuery({
    queryKey: ['budgets'],
    queryFn: listBudgets,
    enabled: useAuthStore.getState().isAuthenticated,
  })
}

export function useCreateBudget() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createBudget,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['budgets'] }),
  })
}

export function useDeleteBudget() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteBudget,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['budgets'] }),
  })
}
