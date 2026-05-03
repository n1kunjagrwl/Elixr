import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { formatCompactINR } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useBudgets } from '@/hooks/useBudgets'

function Skeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="space-y-1.5">
          <div className="flex justify-between">
            <div className="h-3.5 w-24 animate-pulse rounded bg-muted" />
            <div className="h-3.5 w-20 animate-pulse rounded bg-muted" />
          </div>
          <div className="h-2 animate-pulse rounded-full bg-muted" />
        </div>
      ))}
    </div>
  )
}

export function BudgetStatusWidget() {
  const { data: budgets, isLoading } = useBudgets()

  const sorted = [...(budgets ?? [])].sort(
    (a, b) => b.current_spend_paise / b.limit_paise - a.current_spend_paise / a.limit_paise
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Budgets</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && !budgets ? (
          <Skeleton />
        ) : sorted.length === 0 ? (
          <div className="py-4 text-center text-sm text-muted-foreground">No budgets set</div>
        ) : (
          sorted.map((budget) => {
            const pct = Math.min((budget.current_spend_paise / budget.limit_paise) * 100, 100)
            const isOver = budget.current_spend_paise >= budget.limit_paise
            const isNear = pct >= 80 && !isOver

            return (
              <div key={budget.id} className="space-y-1.5" data-testid={`budget-row-${budget.id}`}>
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{budget.category_name}</span>
                  <span
                    className={cn(
                      'text-xs',
                      isOver
                        ? 'text-destructive'
                        : isNear
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-muted-foreground'
                    )}
                  >
                    {formatCompactINR(budget.current_spend_paise)} / {formatCompactINR(budget.limit_paise)}
                  </span>
                </div>
                <Progress
                  value={pct}
                  indicatorClassName={cn(isOver && 'bg-destructive', isNear && 'bg-amber-500')}
                />
              </div>
            )
          })
        )}
      </CardContent>
    </Card>
  )
}
