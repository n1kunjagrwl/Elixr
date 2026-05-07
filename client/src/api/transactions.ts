import api from './client'
import type { Transaction } from '@/types'

export interface TransactionFilters {
  from?: string
  to?: string
  account_id?: string
  category_id?: string
  type?: 'debit' | 'credit'
  unreviewed?: boolean
  page?: number
  page_size?: number
}

interface BackendTransactionSummary {
  id: string
  account_id: string
  account_kind: string
  amount: string | number
  currency: string
  date: string
  type: string
  source: string
  raw_description: string | null
  notes: string | null
  account_name: string | null
  primary_category_id: string | null
  primary_category_name: string | null
  primary_category_icon: string | null
  created_at: string | null
  updated_at: string | null
}

function mapTransaction(raw: BackendTransactionSummary): Transaction {
  return {
    id: raw.id,
    account_id: raw.account_id,
    account_label: raw.account_name ?? '',
    date: raw.date,
    description: raw.raw_description ?? '',
    amount_paise: Math.round(parseFloat(String(raw.amount)) * 100) * (raw.type === 'debit' ? -1 : 1),
    category_id: raw.primary_category_id,
    category_name: raw.primary_category_name,
    category_icon: raw.primary_category_icon,
    is_reviewed: raw.primary_category_id !== null,
  }
}

export async function listTransactions(filters: TransactionFilters = {}): Promise<Transaction[]> {
  const { data } = await api.get<{ items: BackendTransactionSummary[] } | BackendTransactionSummary[]>('/transactions', { params: filters })
  const items = Array.isArray(data) ? data : data.items
  return items.map(mapTransaction)
}

export async function getTransaction(id: string): Promise<Transaction> {
  const { data } = await api.get<BackendTransactionSummary>(`/transactions/${id}`)
  return mapTransaction(data)
}

export async function createTransaction(payload: Record<string, unknown>): Promise<unknown> {
  const { data } = await api.post('/transactions', payload)
  return data
}

export async function updateTransaction(id: string, payload: Record<string, unknown>): Promise<unknown> {
  const { data } = await api.patch(`/transactions/${id}`, payload)
  return data
}

export async function getNetPosition(from: string, to: string): Promise<{ income_paise: number; expense_paise: number; net_paise: number }> {
  const { data } = await api.get('/transactions/summary/net', { params: { from, to } })
  return data
}

export async function getSpendingByCategory(from: string, to: string): Promise<Array<{ category_id: string; category_name: string; category_icon: string | null; total_paise: number }>> {
  const { data } = await api.get('/transactions/summary/by-category', { params: { from, to } })
  return data
}

export async function getUnreviewedCount(): Promise<{ count: number }> {
  const { data } = await api.get<{ count: number }>('/transactions/unreviewed/count')
  return data
}
