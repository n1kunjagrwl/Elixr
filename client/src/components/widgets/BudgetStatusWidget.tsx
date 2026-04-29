import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { formatCompactINR } from '@/lib/format'
import { cn } from '@/lib/utils'

const PLACEHOLDER = [
  { id: '1', category_name: 'Food & Dining', limit_paise: 1500000, current_spend_paise: 1350000 },
  { id: '2', category_name: 'Shopping', limit_paise: 1000000, current_spend_paise: 890000 },
  { id: '3', category_name: 'Transport', limit_paise: 500000, current_spend_paise: 210000 },
]

export function BudgetStatusWidget() {
  const sorted = [...PLACEHOLDER].sort(
    (a, b) => b.current_spend_paise / b.limit_paise - a.current_spend_paise / a.limit_paise
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Budgets</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {sorted.map((budget) => {
          const pct = Math.min((budget.current_spend_paise / budget.limit_paise) * 100, 100)
          const isOver = budget.current_spend_paise >= budget.limit_paise
          const isNear = pct >= 80 && !isOver

          return (
            <div key={budget.id} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{budget.category_name}</span>
                <span className={cn('text-xs', isOver ? 'text-destructive' : isNear ? 'text-amber-600 dark:text-amber-400' : 'text-muted-foreground')}>
                  {formatCompactINR(budget.current_spend_paise)} / {formatCompactINR(budget.limit_paise)}
                </span>
              </div>
              <Progress
                value={pct}
                indicatorClassName={cn(
                  isOver && 'bg-destructive',
                  isNear && 'bg-amber-500'
                )}
              />
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
