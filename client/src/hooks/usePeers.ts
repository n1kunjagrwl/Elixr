import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listPeers, createPeer, recordSettlement } from '@/api/peers'
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

export function useRecordSettlement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ peerId }: { peerId: string }) => recordSettlement(peerId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['peers'] }),
  })
}
