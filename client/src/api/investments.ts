import api from './client'
import type { Holding } from '@/types'

export interface PortfolioSummary {
  total_value_paise: number
  invested_paise: number
  pnl_paise: number
  pnl_percent: number
}

export async function listHoldings(): Promise<Holding[]> {
  const { data } = await api.get<Holding[]>('/investments/holdings')
  return data
}

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  const { data } = await api.get<PortfolioSummary>('/investments/summary')
  return data
}

export async function createHolding(payload: Partial<Holding>): Promise<Holding> {
  const { data } = await api.post<Holding>('/investments/holdings', payload)
  return data
}

export async function listSips(): Promise<Array<{ id: string; name: string; amount_paise: number; next_date: string; status: string }>> {
  const { data } = await api.get('/investments/sips')
  return data
}

export async function listFds(): Promise<Array<{ id: string; bank: string; principal_paise: number; rate: number; maturity_date: string; maturity_paise: number }>> {
  const { data } = await api.get('/investments/fds')
  return data
}
