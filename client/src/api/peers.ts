import api from './client'
import type { PeerContact } from '@/types'

export async function listPeers(): Promise<PeerContact[]> {
  const { data } = await api.get<PeerContact[]>('/peers')
  return data
}

export async function createPeer(payload: { name: string; phone?: string }): Promise<PeerContact> {
  const { data } = await api.post<PeerContact>('/peers', payload)
  return data
}

export async function logBalance(peerId: string, amount_paise: number, note?: string): Promise<void> {
  await api.post(`/peers/${peerId}/balances`, { amount_paise, note })
}

export async function recordSettlement(peerId: string, amount_paise: number): Promise<void> {
  await api.post(`/peers/${peerId}/settlements`, { amount_paise })
}
