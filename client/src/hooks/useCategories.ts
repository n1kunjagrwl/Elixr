import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listCategories, listRules, createCategory, createRule, deleteRule } from '@/api/categories'
import { useAuthStore } from '@/store/auth'

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: listCategories,
    enabled: useAuthStore.getState().isAuthenticated,
    staleTime: 5 * 60_000,
  })
}

export function useRules() {
  return useQuery({
    queryKey: ['categorization-rules'],
    queryFn: listRules,
    enabled: useAuthStore.getState().isAuthenticated,
    staleTime: 5 * 60_000,
  })
}

export function useCreateCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createCategory,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['categories'] }),
  })
}

export function useCreateRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createRule,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['categorization-rules'] }),
  })
}

export function useDeleteRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteRule,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['categorization-rules'] }),
  })
}
