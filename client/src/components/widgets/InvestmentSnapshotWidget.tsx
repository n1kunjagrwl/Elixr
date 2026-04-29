import { TrendingUp, TrendingDown } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'

const PLACEHOLDER = {
  total_value_paise: 38500000,
  invested_paise: 32000000,
  pnl_paise: 6500000,
  pnl_percent: 20.3,
}

const ALLOCATION = [
  { label: 'Mutual Funds', pct: 55, color: '#0891b2' },
  { label: 'Stocks', pct: 25, color: '#f97316' },
  { label: 'Gold', pct: 12, color: '#eab308' },
  { label: 'FD', pct: 8, color: '#a855f7' },
]

export function InvestmentSnapshotWidget() {
  const navigate = useNavigate()
  const { total_value_paise, pnl_paise, pnl_percent } = PLACEHOLDER
  const isPositive = pnl_paise >= 0

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle>Investments</CardTitle>
        <button
          onClick={() => navigate('/investments')}
          className="text-xs text-primary"
        >
          View all
        </button>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between mb-4">
          <div>
            <div className="text-2xl font-bold">{formatCompactINR(total_value_paise)}</div>
            <div className={`flex items-center gap-1 text-xs mt-0.5 ${isPositive ? 'text-green-600 dark:text-green-400' : 'text-destructive'}`}>
              {isPositive ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
              <span>+{formatCompactINR(pnl_paise)} ({pnl_percent.toFixed(1)}%)</span>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          {ALLOCATION.map((item) => (
            <div key={item.label} className="flex items-center gap-2">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${item.pct}%`, backgroundColor: item.color }}
                />
              </div>
              <div className="flex items-center gap-1.5 w-28 shrink-0">
                <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                <span className="text-xs text-muted-foreground truncate">{item.label}</span>
                <span className="text-xs font-medium ml-auto">{item.pct}%</span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
