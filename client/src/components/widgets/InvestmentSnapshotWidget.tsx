import { TrendingUp, TrendingDown } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'
import { usePortfolioSummary, useHoldings } from '@/hooks/useInvestments'
import { CHART_COLORS } from '@/lib/constants'

const TYPE_LABELS: Record<string, string> = {
  mutual_fund: 'Mutual Funds',
  stock: 'Stocks',
  crypto: 'Crypto',
  gold: 'Gold',
  fd: 'FD',
  other: 'Other',
}

const TYPE_COLORS: Record<string, string> = {
  mutual_fund: '#0891b2',
  stock: '#f97316',
  gold: '#eab308',
  fd: '#a855f7',
  crypto: '#22c55e',
  other: '#3b82f6',
}

function Skeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between mb-4">
        <div className="space-y-1.5">
          <div className="h-8 w-24 animate-pulse rounded bg-muted" />
          <div className="h-3.5 w-28 animate-pulse rounded bg-muted" />
        </div>
      </div>
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="h-1.5 flex-1 animate-pulse rounded-full bg-muted" />
            <div className="h-3 w-24 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function InvestmentSnapshotWidget() {
  const navigate = useNavigate()
  const { data: summary, isLoading: summaryLoading } = usePortfolioSummary()
  const { data: holdings, isLoading: holdingsLoading } = useHoldings()

  const isLoading = summaryLoading || holdingsLoading

  const totalValuePaise = summary?.total_value_paise ?? 0
  const pnlPaise = summary?.pnl_paise ?? 0
  const pnlPercent = summary?.pnl_percent ?? 0
  const isPositive = pnlPaise >= 0

  const allocation = (() => {
    if (!holdings || holdings.length === 0) return []
    const byType: Record<string, number> = {}
    for (const h of holdings) {
      byType[h.type] = (byType[h.type] ?? 0) + h.current_value_paise
    }
    const total = Object.values(byType).reduce((s, v) => s + v, 0)
    return Object.entries(byType)
      .sort(([, a], [, b]) => b - a)
      .map(([type, value]) => ({
        label: TYPE_LABELS[type] ?? type,
        pct: total > 0 ? Math.round((value / total) * 100) : 0,
        color: TYPE_COLORS[type] ?? CHART_COLORS[0],
      }))
  })()

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle>Investments</CardTitle>
        <button onClick={() => navigate('/investments')} className="text-xs text-primary">
          View all
        </button>
      </CardHeader>
      <CardContent>
        {isLoading && !summary ? (
          <Skeleton />
        ) : (
          <>
            <div className="flex items-end justify-between mb-4">
              <div>
                <div className="text-2xl font-bold" data-testid="portfolio-total">
                  {formatCompactINR(totalValuePaise)}
                </div>
                {pnlPaise !== 0 && (
                  <div
                    className={`flex items-center gap-1 text-xs mt-0.5 ${isPositive ? 'text-green-600 dark:text-green-400' : 'text-destructive'}`}
                    data-testid="portfolio-pnl"
                  >
                    {isPositive ? (
                      <TrendingUp className="h-3.5 w-3.5" />
                    ) : (
                      <TrendingDown className="h-3.5 w-3.5" />
                    )}
                    <span>
                      {isPositive ? '+' : ''}
                      {formatCompactINR(pnlPaise)} ({pnlPercent.toFixed(1)}%)
                    </span>
                  </div>
                )}
              </div>
            </div>

            {allocation.length > 0 ? (
              <div className="space-y-2" data-testid="portfolio-allocation">
                {allocation.map((item) => (
                  <div key={item.label} className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${item.pct}%`, backgroundColor: item.color }}
                      />
                    </div>
                    <div className="flex items-center gap-1.5 w-28 shrink-0">
                      <span
                        className="h-2 w-2 rounded-full shrink-0"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="text-xs text-muted-foreground truncate">{item.label}</span>
                      <span className="text-xs font-medium ml-auto">{item.pct}%</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-4 text-center text-sm text-muted-foreground">No holdings added</div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
