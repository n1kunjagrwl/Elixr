import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'
import { CHART_COLORS } from '@/lib/constants'

const PLACEHOLDER = [
  { name: 'Food & Dining', value: 120000 },
  { name: 'Transport', value: 45000 },
  { name: 'Shopping', value: 89000 },
  { name: 'Utilities', value: 32000 },
  { name: 'Entertainment', value: 28000 },
]

export function SpendingBreakdownWidget() {
  const total = PLACEHOLDER.reduce((s, d) => s + d.value, 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Spending Breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4">
          <div className="h-36 w-36 shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={PLACEHOLDER}
                  cx="50%"
                  cy="50%"
                  innerRadius={38}
                  outerRadius={58}
                  dataKey="value"
                  strokeWidth={2}
                  stroke="var(--color-background)"
                >
                  {PLACEHOLDER.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="flex-1 space-y-2 min-w-0">
            {PLACEHOLDER.slice(0, 4).map((item, i) => (
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
            {PLACEHOLDER.length > 4 && (
              <div className="text-xs text-muted-foreground">+{PLACEHOLDER.length - 4} more</div>
            )}
            <div className="border-t pt-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Total</span>
                <span className="font-semibold">{formatCompactINR(total)}</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
