import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { ACCENT_OKLCH } from '@/lib/constants'
import type { Theme, AccentColor } from '@/types'

interface ThemeStore {
  theme: Theme
  accent: AccentColor
  setTheme: (theme: Theme) => void
  setAccent: (accent: AccentColor) => void
}

function applyTheme(theme: Theme) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const isDark = theme === 'dark' || (theme === 'system' && prefersDark)
  document.documentElement.classList.toggle('dark', isDark)
}

function applyAccent(accent: AccentColor) {
  const oklch = ACCENT_OKLCH[accent]
  const root = document.documentElement.style
  root.setProperty('--primary', `oklch(${oklch})`)
  root.setProperty('--accent', `oklch(${oklch})`)
  root.setProperty('--ring', `oklch(${oklch})`)
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      theme: 'system',
      accent: 'teal',
      setTheme: (theme) => {
        set({ theme })
        applyTheme(theme)
      },
      setAccent: (accent) => {
        set({ accent })
        applyAccent(accent)
      },
    }),
    { name: 'elixir-theme' }
  )
)

// Apply on module load
if (typeof window !== 'undefined') {
  const { theme, accent } = useThemeStore.getState()
  applyTheme(theme)
  applyAccent(accent)

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (useThemeStore.getState().theme === 'system') applyTheme('system')
  })
}
