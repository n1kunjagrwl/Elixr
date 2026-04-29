import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { DashboardWidget, WidgetId } from '@/types'

const DEFAULT_WIDGETS: DashboardWidget[] = [
  { id: 'attention', label: 'Attention', visible: true, order: 0 },
  { id: 'net-position', label: 'Net Position', visible: true, order: 1 },
  { id: 'spending-breakdown', label: 'Spending Breakdown', visible: true, order: 2 },
  { id: 'budget-status', label: 'Budget Status', visible: true, order: 3 },
  { id: 'recent-transactions', label: 'Recent Transactions', visible: true, order: 4 },
  { id: 'investment-snapshot', label: 'Investments', visible: true, order: 5 },
  { id: 'peer-balances', label: 'Peer Balances', visible: true, order: 6 },
]

interface DashboardStore {
  widgets: DashboardWidget[]
  setWidgetOrder: (ids: WidgetId[]) => void
  toggleWidget: (id: WidgetId) => void
  resetLayout: () => void
}

export const useDashboardStore = create<DashboardStore>()(
  persist(
    (set) => ({
      widgets: DEFAULT_WIDGETS,
      setWidgetOrder: (ids) =>
        set((state) => ({
          widgets: ids.map((id, order) => ({
            ...state.widgets.find((w) => w.id === id)!,
            order,
          })),
        })),
      toggleWidget: (id) =>
        set((state) => ({
          widgets: state.widgets.map((w) => (w.id === id ? { ...w, visible: !w.visible } : w)),
        })),
      resetLayout: () => set({ widgets: DEFAULT_WIDGETS }),
    }),
    { name: 'elixir-dashboard' }
  )
)
