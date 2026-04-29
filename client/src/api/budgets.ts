import api from './client'
import type { BudgetGoal } from '@/types'

export async function listBudgets(): Promise<BudgetGoal[]> {
  const { data } = await api.get<BudgetGoal[]>('/budgets')
  return data
}

export async function createBudget(payload: {
  category_id: string
  limit_paise: number
  period: 'monthly' | 'weekly'
}): Promise<BudgetGoal> {
  const { data } = await api.post<BudgetGoal>('/budgets', payload)
  return data
}

export async function updateBudget(id: string, payload: Partial<BudgetGoal>): Promise<BudgetGoal> {
  const { data } = await api.patch<BudgetGoal>(`/budgets/${id}`, payload)
  return data
}

export async function deleteBudget(id: string): Promise<void> {
  await api.delete(`/budgets/${id}`)
}
