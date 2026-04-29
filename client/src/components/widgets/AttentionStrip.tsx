import { AlertCircle, X } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

interface AttentionItem {
  id: string
  message: string
  action?: string
}

const PLACEHOLDER_ITEMS: AttentionItem[] = [
  { id: '1', message: '3 transactions need your review', action: 'Review' },
  { id: '2', message: 'Food budget is 90% used this month' },
]

export function AttentionStrip() {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())
  const visible = PLACEHOLDER_ITEMS.filter((i) => !dismissed.has(i.id))

  if (visible.length === 0) return null

  return (
    <div className="space-y-2">
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
            {item.action && (
              <button className="text-xs font-semibold text-primary hover:underline">{item.action}</button>
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
