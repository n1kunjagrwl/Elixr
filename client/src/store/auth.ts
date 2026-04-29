import { create } from 'zustand'
import { setAccessToken } from '@/api/client'

interface AuthState {
  isAuthenticated: boolean
  isBootstrapping: boolean
  userId: string | null
  setToken: (token: string | null, userId?: string | null) => void
  setBootstrapping: (v: boolean) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  isBootstrapping: true,
  userId: null,
  setToken: (token, userId = null) => {
    setAccessToken(token)
    set({ isAuthenticated: !!token, userId: token ? userId : null })
  },
  setBootstrapping: (isBootstrapping) => set({ isBootstrapping }),
}))
