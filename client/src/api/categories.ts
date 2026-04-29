import api from './client'
import type { Category } from '@/types'

export async function listCategories(): Promise<Category[]> {
  const { data } = await api.get<Category[]>('/categories')
  return data
}

export async function createCategory(payload: { name: string; icon: string; color: string }): Promise<Category> {
  const { data } = await api.post<Category>('/categories', payload)
  return data
}

export interface CategorizationRule {
  id: string
  pattern: string
  category_id: string
  category_name: string
}

export async function listRules(): Promise<CategorizationRule[]> {
  const { data } = await api.get<CategorizationRule[]>('/categorization-rules')
  return data
}

export async function createRule(payload: { pattern: string; category_id: string }): Promise<CategorizationRule> {
  const { data } = await api.post<CategorizationRule>('/categorization-rules', payload)
  return data
}

export async function deleteRule(id: string): Promise<void> {
  await api.delete(`/categorization-rules/${id}`)
}
