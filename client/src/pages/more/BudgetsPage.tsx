import { useState } from 'react'
import { ChevronLeft, Plus } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { Sheet, SheetContent, SheetPortal, SheetOverlay } from '@/components/ui/sheet'
import { formatCompactINR } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useBudgets, useCreateBudget } from '@/hooks/useBudgets'
import { useCategories } from '@/hooks/useCategories'

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

function CreateBudgetSheet({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const { data: categories } = useCategories()
  const createBudget = useCreateBudget()
  const [categoryId, setCategoryId] = useState('')
  const [limit, setLimit] = useState('')
  const [period, setPeriod] = useState<'monthly' | 'weekly'>('monthly')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const limitNum = parseFloat(limit)
    if (!categoryId || isNaN(limitNum) || limitNum <= 0) return

    createBudget.mutate(
      {
        category_id: categoryId,
        limit_paise: Math.round(limitNum * 100),
        period,
      },
      {
        onSuccess: () => {
          setCategoryId('')
          setLimit('')
          setPeriod('monthly')
          onOpenChange(false)
        },
      }
    )
  }

  const expenseCategories = (categories ?? [])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetPortal>
        <SheetOverlay />
        <SheetContent side="bottom" className="rounded-t-2xl px-4 pb-8 pt-4">
          <div className="mb-4 h-1 w-10 rounded-full bg-muted mx-auto" />
          <h2 className="mb-4 text-base font-semibold">Create Budget</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Category</label>
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                required
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              >
                <option value="">Select category…</option>
                {expenseCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.icon} {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Limit (₹)</label>
              <input
                type="number"
                min="1"
                step="1"
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                required
                placeholder="e.g. 5000"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Period</label>
              <div className="flex gap-2">
                {(['monthly', 'weekly'] as const).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPeriod(p)}
                    className={`flex-1 rounded-lg border py-2 text-sm font-medium capitalize transition-colors ${
                      period === p
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={!categoryId || !limit || createBudget.isPending}
              className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            >
              {createBudget.isPending ? 'Saving…' : 'Create Budget'}
            </button>
          </form>
        </SheetContent>
      </SheetPortal>
    </Sheet>
  )
}

export default function BudgetsPage() {
  const navigate = useNavigate()
  const { data: budgets, isLoading } = useBudgets()
  const [createOpen, setCreateOpen] = useState(false)

  return (
    <div>
      <header className="flex items-center justify-between px-2 py-3 pt-safe">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/more')}
            className="p-2 text-muted-foreground"
            aria-label="Back"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-semibold">Budgets</h1>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-1 p-2 text-primary"
          aria-label="Add budget"
        >
          <Plus className="h-5 w-5" />
        </button>
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
                    <span>{formatCompactINR(budget.current_spend_paise)} spent</span>
                    <span>{formatCompactINR(budget.limit_paise)} limit</span>
                  </div>
                </CardContent>
              </Card>
            )
          })
        )}
      </div>

      <CreateBudgetSheet open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  )
}
