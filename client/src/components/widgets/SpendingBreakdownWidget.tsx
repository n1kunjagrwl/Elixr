import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'
import { CHART_COLORS } from '@/lib/constants'
import { useSpendingByCategory } from '@/hooks/useTransactions'

function Skeleton() {
  return (
    <div className="flex items-center gap-4">
      <div className="h-36 w-36 shrink-0 animate-pulse rounded-full bg-muted" />
      <div className="flex-1 space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center justify-between gap-2">
            <div className="h-3 w-24 animate-pulse rounded bg-muted" />
            <div className="h-3 w-12 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function SpendingBreakdownWidget({ from, to }: { from: Date; to: Date }) {
  const { data, isLoading } = useSpendingByCategory(from, to)

  const chartData = (data ?? [])
    .filter((d) => d.total_paise > 0)
    .sort((a, b) => b.total_paise - a.total_paise)
    .map((d) => ({ name: d.category_name, value: d.total_paise }))

  const total = chartData.reduce((s, d) => s + d.value, 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Spending Breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && !data ? (
          <Skeleton />
        ) : chartData.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            No spending data for this period
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <div className="h-36 w-36 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={38}
                    outerRadius={58}
                    dataKey="value"
                    strokeWidth={2}
                    stroke="var(--color-background)"
                  >
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="flex-1 space-y-2 min-w-0" data-testid="spending-legend">
              {chartData.slice(0, 4).map((item, i) => (
                <div key={item.name} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                    />
                    <span className="truncate text-xs text-muted-foreground">{item.name}</span>
                  </div>
                  <span className="shrink-0 text-xs font-medium">{formatCompactINR(item.value)}</span>
                </div>
              ))}
              {chartData.length > 4 && (
                <div className="text-xs text-muted-foreground">+{chartData.length - 4} more</div>
              )}
              <div className="border-t pt-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Total</span>
                  <span className="font-semibold" data-testid="spending-total">
                    {formatCompactINR(total)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
