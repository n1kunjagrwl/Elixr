import api from './client'
import type { Notification } from '@/types'

export async function listNotifications(): Promise<Notification[]> {
  const { data } = await api.get<Notification[]>('/notifications')
  return data
}

export async function markAllRead(): Promise<void> {
  await api.patch('/notifications/read-all')
}

export async function markRead(id: string): Promise<void> {
  await api.patch(`/notifications/${id}/read`)
}

export async function getUnreadCount(): Promise<{ count: number }> {
  const { data } = await api.get<{ count: number }>('/notifications/unread-count')
  return data
}
