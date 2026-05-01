import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listTransactions,
  updateTransaction,
  getNetPosition,
  getSpendingByCategory,
  getUnreviewedCount,
  type TransactionFilters,
} from '@/api/transactions'
import { useAuthStore } from '@/store/auth'
import { format } from 'date-fns'

function enabled() {
  return useAuthStore.getState().isAuthenticated
}

export function useTransactions(filters: TransactionFilters = {}) {
  return useQuery({
    queryKey: ['transactions', 'list', filters],
    queryFn: () => listTransactions(filters),
    enabled: enabled(),
  })
}

export function useRecentTransactions(limit = 5) {
  return useQuery({
    queryKey: ['transactions', 'recent', limit],
    queryFn: () => listTransactions({ page_size: limit }),
    enabled: enabled(),
  })
}

export function useNetPosition(from: Date, to: Date) {
  const fromStr = format(from, 'yyyy-MM-dd')
  const toStr = format(to, 'yyyy-MM-dd')
  return useQuery({
    queryKey: ['net-position', fromStr, toStr],
    queryFn: () => getNetPosition(fromStr, toStr),
    enabled: enabled(),
  })
}

export function useSpendingByCategory(from: Date, to: Date) {
  const fromStr = format(from, 'yyyy-MM-dd')
  const toStr = format(to, 'yyyy-MM-dd')
  return useQuery({
    queryKey: ['spending-by-category', fromStr, toStr],
    queryFn: () => getSpendingByCategory(fromStr, toStr),
    enabled: enabled(),
  })
}

export function useUnreviewedCount() {
  return useQuery({
    queryKey: ['transactions', 'unreviewed-count'],
    queryFn: getUnreviewedCount,
    enabled: enabled(),
    refetchInterval: 30_000,
  })
}

export function useUpdateTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Parameters<typeof updateTransaction>[1]) =>
      updateTransaction(id, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['transactions'] })
    },
  })
}
