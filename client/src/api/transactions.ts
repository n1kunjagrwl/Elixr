import api from './client'
import type { Transaction } from '@/types'

export interface TransactionFilters {
  from?: string
  to?: string
  account_id?: string
  category_id?: string
  type?: 'debit' | 'credit'
  unreviewed?: boolean
  limit?: number
  offset?: number
}

export async function listTransactions(filters: TransactionFilters = {}): Promise<Transaction[]> {
  const { data } = await api.get<Transaction[]>('/transactions', { params: filters })
  return data
}

export async function getTransaction(id: string): Promise<Transaction> {
  const { data } = await api.get<Transaction>(`/transactions/${id}`)
  return data
}

export async function createTransaction(payload: Partial<Transaction>): Promise<Transaction> {
  const { data } = await api.post<Transaction>('/transactions', payload)
  return data
}

export async function updateTransaction(id: string, payload: Partial<Transaction>): Promise<Transaction> {
  const { data } = await api.patch<Transaction>(`/transactions/${id}`, payload)
  return data
}

export async function getNetPosition(from: string, to: string): Promise<{ income_paise: number; expense_paise: number; net_paise: number }> {
  const { data } = await api.get('/transactions/summary/net', { params: { from, to } })
  return data
}

export async function getSpendingByCategory(from: string, to: string): Promise<Array<{ category_id: string; category_name: string; total_paise: number }>> {
  const { data } = await api.get('/transactions/summary/by-category', { params: { from, to } })
  return data
}

export async function getUnreviewedCount(): Promise<{ count: number }> {
  const { data } = await api.get<{ count: number }>('/transactions/unreviewed/count')
  return data
}
