import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listAccounts, createBankAccount, createCreditCard, uploadStatement } from '@/api/accounts'
import { useAuthStore } from '@/store/auth'

export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: listAccounts,
    enabled: useAuthStore.getState().isAuthenticated,
    staleTime: 5 * 60_000,
  })
}

export function useCreateBankAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createBankAccount,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['accounts'] }),
  })
}

export function useCreateCreditCard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createCreditCard,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['accounts'] }),
  })
}

export function useUploadStatement() {
  return useMutation({
    mutationFn: ({ accountId, file }: { accountId: string; file: File }) =>
      uploadStatement(accountId, file),
  })
}
