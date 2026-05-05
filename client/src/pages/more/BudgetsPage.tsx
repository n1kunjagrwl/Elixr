import { ChevronLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useBudgets } from '@/hooks/useBudgets'

function BudgetSkeleton() {
  return (
    <Card>
      <CardContent className="py-3 space-y-2">
        <div className="flex justify-between">
          <div className="h-3.5 w-28 animate-pulse rounded bg-muted" />
          <div className="h-3 w-20 animate-pulse rounded bg-muted" />
        </div>
        <div className="h-2 w-full animate-pulse rounded-full bg-muted" />
      </CardContent>
    </Card>
  )
}

export default function BudgetsPage() {
  const navigate = useNavigate()
  const { data: budgets, isLoading } = useBudgets()

  return (
    <div>
      <header className="flex items-center gap-2 px-2 py-3 pt-safe">
        <button
          onClick={() => navigate('/more')}
          className="p-2 text-muted-foreground"
          aria-label="Back"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h1 className="text-lg font-semibold">Budgets</h1>
      </header>

      <div className="px-4 space-y-2">
        {isLoading && !budgets ? (
          Array.from({ length: 3 }).map((_, i) => <BudgetSkeleton key={i} />)
        ) : (budgets ?? []).length === 0 ? (
          <div
            className="flex flex-col items-center justify-center gap-2 py-16 text-center text-muted-foreground"
            data-testid="empty-state"
          >
            <p className="text-sm">No budgets set yet.</p>
            <p className="text-xs">Tap + to create your first budget.</p>
          </div>
        ) : (
          (budgets ?? []).map((budget) => {
            const pct = Math.min(
              Math.round((budget.current_spend_paise / budget.limit_paise) * 100),
              100
            )
            const overBudget = budget.current_spend_paise > budget.limit_paise
            return (
              <Card key={budget.id} data-testid={`budget-row-${budget.id}`}>
                <CardContent className="py-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">{budget.category_name}</div>
                    <div className="text-xs text-muted-foreground capitalize">{budget.period}</div>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all',
                        overBudget ? 'bg-destructive' : 'bg-primary'
                      )}
                      style={{ width: `${pct}%` }}
                      data-testid={`budget-bar-${budget.id}`}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>
                      {formatCompactINR(budget.current_spend_paise)} spent
                    </span>
                    <span>{formatCompactINR(budget.limit_paise)} limit</span>
                  </div>
                </CardContent>
              </Card>
            )
          })
        )}
      </div>
    </div>
  )
}
