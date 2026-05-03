import { useState } from 'react'
import { format } from 'date-fns'
import { Bell } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { AttentionStrip } from '@/components/widgets/AttentionStrip'
import { NetPositionWidget } from '@/components/widgets/NetPositionWidget'
import { SpendingBreakdownWidget } from '@/components/widgets/SpendingBreakdownWidget'
import { BudgetStatusWidget } from '@/components/widgets/BudgetStatusWidget'
import { RecentTransactionsWidget } from '@/components/widgets/RecentTransactionsWidget'
import { InvestmentSnapshotWidget } from '@/components/widgets/InvestmentSnapshotWidget'
import { PeerBalancesWidget } from '@/components/widgets/PeerBalancesWidget'
import { useDashboardStore } from '@/store/dashboard'
import { useUnreadCount } from '@/hooks/useNotifications'
import { startOfMonth, endOfMonth } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { WidgetId } from '@/types'

const PRESETS = ['This Month', 'Last Month', '3 Months', 'This Year'] as const
type Preset = (typeof PRESETS)[number]

function presetDateRange(preset: Preset, now: Date): { from: Date; to: Date } {
  switch (preset) {
    case 'This Month':
      return { from: startOfMonth(now), to: endOfMonth(now) }
    case 'Last Month': {
      const last = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      return { from: startOfMonth(last), to: endOfMonth(last) }
    }
    case '3 Months': {
      const threeBack = new Date(now.getFullYear(), now.getMonth() - 2, 1)
      return { from: startOfMonth(threeBack), to: endOfMonth(now) }
    }
    case 'This Year':
      return { from: new Date(now.getFullYear(), 0, 1), to: endOfMonth(now) }
  }
}

function WidgetRenderer({ id, dateRange }: { id: WidgetId; dateRange: { from: Date; to: Date } }) {
  switch (id) {
    case 'attention':
      return <AttentionStrip />
    case 'net-position':
      return <NetPositionWidget from={dateRange.from} to={dateRange.to} />
    case 'spending-breakdown':
      return <SpendingBreakdownWidget from={dateRange.from} to={dateRange.to} />
    case 'budget-status':
      return <BudgetStatusWidget />
    case 'recent-transactions':
      return <RecentTransactionsWidget />
    case 'investment-snapshot':
      return <InvestmentSnapshotWidget />
    case 'peer-balances':
      return <PeerBalancesWidget />
  }
}

export default function HomePage() {
  const [preset, setPreset] = useState<Preset>('This Month')
  const widgets = useDashboardStore((s) => s.widgets)
    .filter((w) => w.visible)
    .sort((a, b) => a.order - b.order)

  const now = new Date()
  const dateRange = presetDateRange(preset, now)
  const { data: unreadData } = useUnreadCount()
  const hasUnread = (unreadData?.count ?? 0) > 0

  return (
    <div>
      <Header
        title={format(now, 'MMMM yyyy')}
        action={
          <button className="relative p-1" aria-label="Notifications">
            <Bell className="h-5 w-5 text-muted-foreground" />
            {hasUnread && (
              <span className="absolute right-0 top-0 h-2 w-2 rounded-full bg-primary" />
            )}
          </button>
        }
      />

      <div className="px-4 pb-2">
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
          {PRESETS.map((p) => (
            <button
              key={p}
              onClick={() => setPreset(p)}
              className={cn(
                'shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors',
                p === preset
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3 px-4 pb-4">
        {widgets.map((w) => (
          <WidgetRenderer key={w.id} id={w.id} dateRange={dateRange} />
        ))}
      </div>
    </div>
  )
}
