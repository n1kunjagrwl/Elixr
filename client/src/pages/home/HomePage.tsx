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
import { cn } from '@/lib/utils'
import type { WidgetId } from '@/types'

const PRESETS = ['This Month', 'Last Month', '3 Months', 'This Year'] as const
type Preset = (typeof PRESETS)[number]

function WidgetRenderer({ id }: { id: WidgetId }) {
  switch (id) {
    case 'attention': return <AttentionStrip />
    case 'net-position': return <NetPositionWidget />
    case 'spending-breakdown': return <SpendingBreakdownWidget />
    case 'budget-status': return <BudgetStatusWidget />
    case 'recent-transactions': return <RecentTransactionsWidget />
    case 'investment-snapshot': return <InvestmentSnapshotWidget />
    case 'peer-balances': return <PeerBalancesWidget />
  }
}

export default function HomePage() {
  const [preset, setPreset] = useState<Preset>('This Month')
  const widgets = useDashboardStore((s) => s.widgets)
    .filter((w) => w.visible)
    .sort((a, b) => a.order - b.order)

  const now = new Date()

  return (
    <div>
      <Header
        title={format(now, 'MMMM yyyy')}
        action={
          <button className="relative p-1">
            <Bell className="h-5 w-5 text-muted-foreground" />
            <span className="absolute right-0 top-0 h-2 w-2 rounded-full bg-primary" />
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
          <WidgetRenderer key={w.id} id={w.id} />
        ))}
      </div>
    </div>
  )
}
