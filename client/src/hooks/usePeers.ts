import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listPeers, createPeer, logBalance, recordSettlement } from '@/api/peers'
import { useAuthStore } from '@/store/auth'

export function usePeers() {
  return useQuery({
    queryKey: ['peers'],
    queryFn: listPeers,
    enabled: useAuthStore.getState().isAuthenticated,
  })
}

export function useCreatePeer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createPeer,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['peers'] }),
  })
}

export function useLogBalance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ peerId, amount_paise, note }: { peerId: string; amount_paise: number; note?: string }) =>
      logBalance(peerId, amount_paise, note),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['peers'] }),
  })
}

export function useRecordSettlement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ peerId, amount_paise }: { peerId: string; amount_paise: number }) =>
      recordSettlement(peerId, amount_paise),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['peers'] }),
  })
}
