import api from './client'
import type { Notification } from '@/types'

export async function listNotifications(): Promise<Notification[]> {
  const { data } = await api.get<Notification[]>('/notifications')
  return data
}

export async function markRead(ids: string[]): Promise<void> {
  await api.post('/notifications/mark-read', { ids })
}

export async function getUnreadCount(): Promise<{ count: number }> {
  const { data } = await api.get<{ count: number }>('/notifications/unread-count')
  return data
}
