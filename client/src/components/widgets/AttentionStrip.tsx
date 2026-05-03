import { AlertCircle, X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useUnreviewedCount } from '@/hooks/useTransactions'
import { useNotifications } from '@/hooks/useNotifications'

export function AttentionStrip() {
  const navigate = useNavigate()
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())
  const { data: unreviewedData } = useUnreviewedCount()
  const { data: notifications } = useNotifications()

  const items: Array<{ id: string; message: string; onAction?: () => void; actionLabel?: string }> = []

  const unreviewedCount = unreviewedData?.count ?? 0
  if (unreviewedCount > 0) {
    items.push({
      id: 'unreviewed',
      message: `${unreviewedCount} transaction${unreviewedCount > 1 ? 's' : ''} need your review`,
      onAction: () => navigate('/transactions?unreviewed=true'),
      actionLabel: 'Review',
    })
  }

  for (const n of notifications ?? []) {
    if (!n.is_read) {
      items.push({ id: `notif-${n.id}`, message: n.title })
    }
  }

  const visible = items.filter((i) => !dismissed.has(i.id))

  if (visible.length === 0) return null

  return (
    <div className="space-y-2" data-testid="attention-strip">
      {visible.map((item) => (
        <div
          key={item.id}
          className={cn(
            'flex items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3',
            'dark:border-amber-900 dark:bg-amber-950/30'
          )}
        >
          <div className="flex items-center gap-2 min-w-0">
            <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <span className="text-sm text-amber-900 dark:text-amber-200 truncate">{item.message}</span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {item.onAction && item.actionLabel && (
              <button
                onClick={item.onAction}
                className="text-xs font-semibold text-primary hover:underline"
              >
                {item.actionLabel}
              </button>
            )}
            <button
              onClick={() => setDismissed((s) => new Set([...s, item.id]))}
              className="ml-1 text-amber-600 dark:text-amber-400 hover:text-amber-900"
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
