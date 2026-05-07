import api from './client'
import type { PeerContact } from '@/types'

export async function listPeers(): Promise<PeerContact[]> {
  const { data } = await api.get<PeerContact[]>('/peers/contacts')
  return data
}

export async function createPeer(payload: { name: string; phone?: string }): Promise<PeerContact> {
  const { data } = await api.post<PeerContact>('/peers/contacts', payload)
  return data
}

export async function recordSettlement(peerId: string): Promise<void> {
  await api.post(`/peers/contacts/${peerId}/settle`)
}
