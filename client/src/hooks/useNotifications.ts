import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listNotifications, markRead, getUnreadCount } from '@/api/notifications'
import { useAuthStore } from '@/store/auth'

function enabled() {
  return useAuthStore.getState().isAuthenticated
}

export function useNotifications() {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: listNotifications,
    enabled: enabled(),
    refetchInterval: 60_000,
  })
}

export function useUnreadCount() {
  return useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: getUnreadCount,
    enabled: enabled(),
    refetchInterval: 30_000,
  })
}

export function useMarkRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: markRead,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
}
