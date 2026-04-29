import api from './client'

export async function requestOtp(phone: string): Promise<void> {
  await api.post('/auth/request-otp', { phone })
}

export async function verifyOtp(phone: string, otp: string): Promise<{ access_token: string }> {
  const { data } = await api.post<{ access_token: string }>('/auth/verify-otp', { phone, otp })
  return data
}

export async function refreshSession(): Promise<{ access_token: string }> {
  const { data } = await api.post<{ access_token: string }>('/auth/refresh')
  return data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}
