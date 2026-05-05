import { ChevronLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { formatDate } from '@/lib/format'
import { useEarnings } from '@/hooks/useEarnings'

const SOURCE_TYPE_LABELS: Record<string, string> = {
  salary: 'Salary',
  freelance: 'Freelance',
  rental: 'Rental',
  dividend: 'Dividend',
  interest: 'Interest',
  business: 'Business',
  other: 'Other',
}

function EarningSkeleton() {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-3">
        <div className="flex-1 space-y-1.5">
          <div className="h-3.5 w-32 animate-pulse rounded bg-muted" />
          <div className="h-3 w-20 animate-pulse rounded bg-muted" />
        </div>
        <div className="h-3.5 w-16 animate-pulse rounded bg-muted" />
      </CardContent>
    </Card>
  )
}

export default function EarningsPage() {
  const navigate = useNavigate()
  const { data: earnings, isLoading } = useEarnings()

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
        <h1 className="text-lg font-semibold">Earnings</h1>
      </header>

      <div className="px-4 space-y-2">
        {isLoading && !earnings ? (
          Array.from({ length: 3 }).map((_, i) => <EarningSkeleton key={i} />)
        ) : (earnings ?? []).length === 0 ? (
          <div
            className="flex flex-col items-center justify-center gap-2 py-16 text-center text-muted-foreground"
            data-testid="empty-state"
          >
            <p className="text-sm">No income sources added yet.</p>
            <p className="text-xs">Add salary or other income streams here.</p>
          </div>
        ) : (
          (earnings ?? []).map((earning) => {
            const label =
              earning.source_name ??
              earning.source_label ??
              SOURCE_TYPE_LABELS[earning.source_type] ??
              earning.source_type
            return (
              <Card key={earning.id} data-testid={`earning-row-${earning.id}`}>
                <CardContent className="flex items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{label}</div>
                    <div className="text-xs text-muted-foreground">
                      {SOURCE_TYPE_LABELS[earning.source_type] ?? earning.source_type} ·{' '}
                      {formatDate(earning.date)}
                    </div>
                  </div>
                  <div className="text-sm font-semibold text-green-600 dark:text-green-400">
                    ₹{Number(earning.amount).toLocaleString('en-IN')}
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
