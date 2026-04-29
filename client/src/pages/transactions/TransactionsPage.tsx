import { useState } from 'react'
import { Search, SlidersHorizontal } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { formatCompactINR, formatRelativeDate } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

const CATEGORIES = ['All', 'Food', 'Transport', 'Shopping', 'Bills', 'Salary']

const PLACEHOLDER = [
  { id: '1', description: 'Swiggy Order', category: 'Food', icon: '🍔', date: new Date().toISOString(), amount_paise: -45000, is_reviewed: true },
  { id: '2', description: 'Salary — Think41', category: 'Salary', icon: '💼', date: new Date(Date.now() - 86400000).toISOString(), amount_paise: 8500000, is_reviewed: true },
  { id: '3', description: 'Uber Ride', category: 'Transport', icon: '🚗', date: new Date(Date.now() - 86400000).toISOString(), amount_paise: -18000, is_reviewed: true },
  { id: '4', description: 'Amazon Purchase', category: 'Shopping', icon: '🛒', date: new Date(Date.now() - 2 * 86400000).toISOString(), amount_paise: -129900, is_reviewed: false },
  { id: '5', description: 'Zomato', category: 'Food', icon: '🍕', date: new Date(Date.now() - 2 * 86400000).toISOString(), amount_paise: -38000, is_reviewed: true },
  { id: '6', description: 'HDFC Credit Card Bill', category: 'Bills', icon: '💳', date: new Date(Date.now() - 3 * 86400000).toISOString(), amount_paise: -240000, is_reviewed: true },
  { id: '7', description: 'Ola Cab', category: 'Transport', icon: '🚕', date: new Date(Date.now() - 4 * 86400000).toISOString(), amount_paise: -22000, is_reviewed: true },
  { id: '8', description: 'Electricity Bill', category: 'Bills', icon: '⚡', date: new Date(Date.now() - 5 * 86400000).toISOString(), amount_paise: -89000, is_reviewed: true },
]

export default function TransactionsPage() {
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState('All')

  const filtered = PLACEHOLDER.filter((tx) => {
    const matchesSearch = tx.description.toLowerCase().includes(search.toLowerCase())
    const matchesCategory = activeCategory === 'All' || tx.category === activeCategory
    return matchesSearch && matchesCategory
  })

  return (
    <div>
      <Header
        title="Transactions"
        action={
          <button className="p-1 text-muted-foreground">
            <SlidersHorizontal className="h-5 w-5" />
          </button>
        }
      />

      <div className="px-4 pb-3 space-y-3">
        <div className="flex items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search transactions…"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>

        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={cn(
                'shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors',
                cat === activeCategory
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              )}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <div className="divide-y">
        {filtered.map((tx) => (
          <div key={tx.id} className="flex items-center gap-3 px-4 py-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted text-xl">
              {tx.icon}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-medium">{tx.description}</span>
                {!tx.is_reviewed && (
                  <Badge variant="muted" className="shrink-0 text-[10px]">Review</Badge>
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                {tx.category} · {formatRelativeDate(tx.date)}
              </div>
            </div>
            <div className={cn('shrink-0 text-sm font-semibold', tx.amount_paise < 0 ? 'text-foreground' : 'text-green-600 dark:text-green-400')}>
              {tx.amount_paise < 0 ? '−' : '+'}{formatCompactINR(Math.abs(tx.amount_paise))}
            </div>
          </div>
        ))}

        {filtered.length === 0 && (
          <div className="px-4 py-12 text-center text-sm text-muted-foreground">
            No transactions found
          </div>
        )}
      </div>
    </div>
  )
}
