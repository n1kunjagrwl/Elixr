import api from './client'

export interface EarningSummary {
  id: string
  transaction_id: string | null
  source_id: string | null
  source_type: string
  source_label: string | null
  source_name: string | null
  amount: number
  currency: string
  date: string
  notes: string | null
  created_at: string | null
  updated_at: string | null
}

export interface EarningSource {
  id: string
  name: string
  type: string
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

export async function listEarnings(): Promise<EarningSummary[]> {
  const { data } = await api.get<EarningSummary[]>('/earnings')
  return data
}

export async function listEarningSources(): Promise<EarningSource[]> {
  const { data } = await api.get<EarningSource[]>('/earnings/sources')
  return data
}
