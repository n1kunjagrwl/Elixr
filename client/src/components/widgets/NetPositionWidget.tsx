import { ArrowDown, ArrowUp } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'
import { useNetPosition } from '@/hooks/useTransactions'

function Skeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div className="space-y-1.5">
          <div className="h-9 w-28 animate-pulse rounded bg-muted" />
          <div className="h-3 w-20 animate-pulse rounded bg-muted" />
        </div>
        <div className="space-y-1.5">
          <div className="h-4 w-16 animate-pulse rounded bg-muted ml-auto" />
          <div className="h-4 w-16 animate-pulse rounded bg-muted ml-auto" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="h-16 animate-pulse rounded-lg bg-muted" />
        <div className="h-16 animate-pulse rounded-lg bg-muted" />
      </div>
    </div>
  )
}

export function NetPositionWidget({ from, to }: { from: Date; to: Date }) {
  const { data, isLoading } = useNetPosition(from, to)

  const income_paise = data?.income_paise ?? 0
  const expense_paise = data?.expense_paise ?? 0
  const net = income_paise - expense_paise
  const isPositive = net >= 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>Net Position</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && !data ? (
          <Skeleton />
        ) : (
          <>
            <div className="flex items-end justify-between">
              <div>
                <div
                  className={`text-3xl font-bold ${isPositive ? 'text-foreground' : 'text-destructive'}`}
                  data-testid="net-position-value"
                >
                  {formatCompactINR(net)}
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">This period</div>
              </div>
              <div className="space-y-1 text-right">
                <div className="flex items-center justify-end gap-1 text-sm text-green-600 dark:text-green-400">
                  <ArrowUp className="h-3.5 w-3.5" />
                  <span data-testid="net-position-income">{formatCompactINR(income_paise)}</span>
                </div>
                <div className="flex items-center justify-end gap-1 text-sm text-muted-foreground">
                  <ArrowDown className="h-3.5 w-3.5" />
                  <span data-testid="net-position-expense">{formatCompactINR(expense_paise)}</span>
                </div>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-green-50 p-3 dark:bg-green-950/30">
                <div className="text-xs text-green-700 dark:text-green-400 font-medium">Income</div>
                <div className="text-base font-semibold text-green-700 dark:text-green-300">
                  {formatCompactINR(income_paise)}
                </div>
              </div>
              <div className="rounded-lg bg-muted p-3">
                <div className="text-xs text-muted-foreground font-medium">Expenses</div>
                <div className="text-base font-semibold">{formatCompactINR(expense_paise)}</div>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
