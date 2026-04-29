import { ArrowDown, ArrowUp, Minus } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'

const PLACEHOLDER = {
  income_paise: 8500000,
  expense_paise: 3200000,
}

export function NetPositionWidget() {
  const { income_paise, expense_paise } = PLACEHOLDER
  const net = income_paise - expense_paise
  const isPositive = net >= 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>Net Position</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between">
          <div>
            <div className={`text-3xl font-bold ${isPositive ? 'text-foreground' : 'text-destructive'}`}>
              {formatCompactINR(net)}
            </div>
            <div className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
              {isPositive ? (
                <Minus className="h-3 w-3 text-green-500" />
              ) : (
                <Minus className="h-3 w-3 text-destructive" />
              )}
              <span>This month</span>
            </div>
          </div>
          <div className="space-y-1 text-right">
            <div className="flex items-center justify-end gap-1 text-sm text-green-600 dark:text-green-400">
              <ArrowUp className="h-3.5 w-3.5" />
              <span>{formatCompactINR(income_paise)}</span>
            </div>
            <div className="flex items-center justify-end gap-1 text-sm text-muted-foreground">
              <ArrowDown className="h-3.5 w-3.5" />
              <span>{formatCompactINR(expense_paise)}</span>
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
      </CardContent>
    </Card>
  )
}
