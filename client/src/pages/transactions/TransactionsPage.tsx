import { useState } from 'react'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { Header } from '@/components/layout/Header'
import { formatCompactINR, formatRelativeDate } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { useTransactions } from '@/hooks/useTransactions'
import { useCategories } from '@/hooks/useCategories'
import type { Transaction } from '@/types'

function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b">
      <div className="h-10 w-10 shrink-0 animate-pulse rounded-full bg-muted" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 w-36 animate-pulse rounded bg-muted" />
        <div className="h-3 w-24 animate-pulse rounded bg-muted" />
      </div>
      <div className="h-3.5 w-14 animate-pulse rounded bg-muted" />
    </div>
  )
}

function TransactionRow({ tx }: { tx: Transaction }) {
  const isCredit = tx.amount_paise > 0
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 border-b last:border-0"
      data-testid={`tx-row-${tx.id}`}
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted text-xl">
        {tx.category_icon ?? '💰'}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{tx.description}</span>
          {!tx.is_reviewed && (
            <Badge variant="muted" className="shrink-0 text-[10px]">
              Review
            </Badge>
          )}
        </div>
        <div className="text-xs text-muted-foreground">
          {tx.category_name ?? 'Uncategorised'} · {formatRelativeDate(tx.date)}
        </div>
      </div>
      <div
        className={cn(
          'shrink-0 text-sm font-semibold',
          isCredit ? 'text-green-600 dark:text-green-400' : 'text-foreground'
        )}
      >
        {isCredit ? '+' : '−'}
        {formatCompactINR(Math.abs(tx.amount_paise))}
      </div>
    </div>
  )
}

export default function TransactionsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [activeCategoryId, setActiveCategoryId] = useState<string | null>(null)
  const [showUnreviewed, setShowUnreviewed] = useState(
    searchParams.get('unreviewed') === 'true'
  )

  const { data: transactions, isLoading } = useTransactions({
    category_id: activeCategoryId ?? undefined,
    unreviewed: showUnreviewed || undefined,
    page_size: 50,
  })

  const { data: categories } = useCategories()

  // Text search is applied client-side since the backend has no search param
  const filtered = (transactions ?? []).filter((tx) =>
    tx.description.toLowerCase().includes(search.toLowerCase())
  )

  function clearUnreviewed() {
    setShowUnreviewed(false)
    setSearchParams({}, { replace: true })
  }

  const hasActiveFilters = activeCategoryId !== null || showUnreviewed || search !== ''

  return (
    <div>
      <Header
        title="Transactions"
        action={
          <button className="p-1 text-muted-foreground" aria-label="Filters">
            <SlidersHorizontal className="h-5 w-5" />
          </button>
        }
      />

      <div className="px-4 pb-3 space-y-3">
        {/* Search */}
        <div className="flex items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search transactions…"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            data-testid="search-input"
          />
          {search && (
            <button onClick={() => setSearch('')} className="text-muted-foreground" aria-label="Clear search">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Active filter badges */}
        {showUnreviewed && (
          <div className="flex items-center gap-2" data-testid="unreviewed-filter-badge">
            <span className="flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
              Needs review
              <button onClick={clearUnreviewed} aria-label="Clear unreviewed filter">
                <X className="h-3 w-3 ml-1" />
              </button>
            </span>
          </div>
        )}

        {/* Category chips */}
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none" data-testid="category-chips">
          <button
            onClick={() => setActiveCategoryId(null)}
            className={cn(
              'shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors',
              activeCategoryId === null
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground'
            )}
          >
            All
          </button>
          {(categories ?? []).map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategoryId(cat.id)}
              data-testid={`category-chip-${cat.id}`}
              className={cn(
                'shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors',
                activeCategoryId === cat.id
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              )}
            >
              {cat.name}
            </button>
          ))}
        </div>
      </div>

      {/* Transaction list */}
      <div>
        {isLoading && !transactions ? (
          Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
        ) : filtered.length === 0 ? (
          <div
            className="px-4 py-12 text-center text-sm text-muted-foreground"
            data-testid="empty-state"
          >
            {!hasActiveFilters ? 'No transactions yet' : 'No transactions found'}
          </div>
        ) : (
          filtered.map((tx) => <TransactionRow key={tx.id} tx={tx} />)
        )}
      </div>
    </div>
  )
}
