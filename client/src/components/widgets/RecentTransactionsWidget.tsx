import { useNavigate } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatCompactINR, formatRelativeDate } from '@/lib/format'
import { useRecentTransactions } from '@/hooks/useTransactions'
import { cn } from '@/lib/utils'
import type { Transaction } from '@/types'

// Shown when the API is loading or has errored — keeps the widget useful
// without a backend connection.
const PLACEHOLDER: Transaction[] = [
  { id: '1', account_id: '', account_label: 'HDFC', date: new Date().toISOString(), description: 'Swiggy', amount_paise: -45000, category_id: null, category_name: 'Food & Dining', category_icon: '🍔', is_reviewed: true },
  { id: '2', account_id: '', account_label: 'HDFC', date: new Date(Date.now() - 86400000).toISOString(), description: 'Salary — Think41', amount_paise: 8500000, category_id: null, category_name: 'Salary', category_icon: '💼', is_reviewed: true },
  { id: '3', account_id: '', account_label: 'HDFC', date: new Date(Date.now() - 86400000).toISOString(), description: 'Uber', amount_paise: -18000, category_id: null, category_name: 'Transport', category_icon: '🚗', is_reviewed: true },
  { id: '4', account_id: '', account_label: 'HDFC', date: new Date(Date.now() - 2 * 86400000).toISOString(), description: 'Amazon', amount_paise: -129900, category_id: null, category_name: 'Shopping', category_icon: '🛒', is_reviewed: false },
  { id: '5', account_id: '', account_label: 'HDFC', date: new Date(Date.now() - 3 * 86400000).toISOString(), description: 'HDFC Credit Card Bill', amount_paise: -240000, category_id: null, category_name: 'Bills', category_icon: '💳', is_reviewed: true },
]

function TransactionRow({ tx, isLast }: { tx: Transaction; isLast: boolean }) {
  const isCredit = tx.amount_paise > 0
  return (
    <li className={cn('flex items-center gap-3 px-4 py-3', !isLast && 'border-b')}>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-lg">
        {tx.category_icon ?? '💰'}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{tx.description}</div>
        <div className="text-xs text-muted-foreground">
          {tx.category_name ?? 'Uncategorised'} · {formatRelativeDate(tx.date)}
        </div>
      </div>
      <div className={cn('shrink-0 text-sm font-semibold', isCredit ? 'text-green-600 dark:text-green-400' : 'text-foreground')}>
        {isCredit ? '+' : '−'}{formatCompactINR(Math.abs(tx.amount_paise))}
      </div>
    </li>
  )
}

function SkeletonRow() {
  return (
    <li className="flex items-center gap-3 border-b px-4 py-3 last:border-0">
      <div className="h-9 w-9 shrink-0 animate-pulse rounded-full bg-muted" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 w-32 animate-pulse rounded bg-muted" />
        <div className="h-3 w-20 animate-pulse rounded bg-muted" />
      </div>
      <div className="h-3.5 w-16 animate-pulse rounded bg-muted" />
    </li>
  )
}

export function RecentTransactionsWidget() {
  const navigate = useNavigate()
  const { data, isLoading, isError } = useRecentTransactions(5)

  const transactions = data ?? (isError ? PLACEHOLDER : null)

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle>Recent Transactions</CardTitle>
        <button onClick={() => navigate('/transactions')} className="flex items-center gap-0.5 text-xs text-primary">
          See all <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </CardHeader>
      <CardContent className="p-0">
        <ul>
          {isLoading && !transactions
            ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
            : (transactions ?? []).map((tx, i, arr) => (
                <TransactionRow key={tx.id} tx={tx} isLast={i === arr.length - 1} />
              ))}
        </ul>
      </CardContent>
    </Card>
  )
}
