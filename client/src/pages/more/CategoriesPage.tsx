import { ChevronLeft, Zap } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { useCategories, useRules } from '@/hooks/useCategories'

export default function CategoriesPage() {
  const navigate = useNavigate()
  const { data: categories, isLoading: loadingCats } = useCategories()
  const { data: rules, isLoading: loadingRules } = useRules()

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
        <h1 className="text-lg font-semibold">Categories &amp; Rules</h1>
      </header>

      <div className="px-4 space-y-5">
        {/* Categories */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Categories
          </h2>
          {loadingCats && !categories ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-10 animate-pulse rounded-lg bg-muted" />
              ))}
            </div>
          ) : (categories ?? []).length === 0 ? (
            <div
              className="py-8 text-center text-sm text-muted-foreground"
              data-testid="categories-empty-state"
            >
              No custom categories yet.
            </div>
          ) : (
            <div className="space-y-2">
              {(categories ?? []).map((cat) => (
                <Card key={cat.id} data-testid={`category-row-${cat.id}`}>
                  <CardContent className="flex items-center gap-3 py-2.5">
                    <span className="text-lg">{cat.icon}</span>
                    <span className="flex-1 text-sm font-medium">{cat.name}</span>
                    {cat.is_system && (
                      <span className="text-xs text-muted-foreground">System</span>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>

        {/* Auto-tagging Rules */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Auto-tagging Rules
          </h2>
          {loadingRules && !rules ? (
            <div className="space-y-2">
              {Array.from({ length: 2 }).map((_, i) => (
                <div key={i} className="h-10 animate-pulse rounded-lg bg-muted" />
              ))}
            </div>
          ) : (rules ?? []).length === 0 ? (
            <div
              className="py-8 text-center text-sm text-muted-foreground"
              data-testid="rules-empty-state"
            >
              No auto-tagging rules yet.
            </div>
          ) : (
            <div className="space-y-2">
              {(rules ?? []).map((rule) => (
                <Card key={rule.id} data-testid={`rule-row-${rule.id}`}>
                  <CardContent className="flex items-center gap-3 py-2.5">
                    <Zap className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-mono">{rule.pattern}</span>
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0">
                      → {rule.category_name}
                    </span>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
