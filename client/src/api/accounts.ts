import api from './client'
import type { Account } from '@/types'

export async function listAccounts(): Promise<Account[]> {
  const { data } = await api.get<Account[]>('/accounts')
  return data
}

export async function createBankAccount(payload: { label: string; bank_name: string; last4: string }): Promise<Account> {
  const { data } = await api.post<Account>('/accounts/bank', payload)
  return data
}

export async function uploadStatement(accountId: string, file: File): Promise<{ job_id: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('account_id', accountId)
  const { data } = await api.post<{ job_id: string }>('/statements/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
