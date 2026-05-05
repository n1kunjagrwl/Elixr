import { useState } from 'react'
import { ChevronLeft, Zap, Plus } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { Sheet, SheetContent, SheetPortal, SheetOverlay } from '@/components/ui/sheet'
import { useCategories, useRules, useCreateCategory, useCreateRule } from '@/hooks/useCategories'

function AddCategorySheet({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const createCategory = useCreateCategory()
  const [name, setName] = useState('')
  const [icon, setIcon] = useState('')
  const [color, setColor] = useState('#6366f1')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim() || !icon.trim()) return
    createCategory.mutate(
      { name: name.trim(), icon: icon.trim(), color },
      {
        onSuccess: () => {
          setName('')
          setIcon('')
          setColor('#6366f1')
          onOpenChange(false)
        },
      }
    )
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetPortal>
        <SheetOverlay />
        <SheetContent side="bottom" className="rounded-t-2xl px-4 pb-8 pt-4">
          <div className="mb-4 h-1 w-10 rounded-full bg-muted mx-auto" />
          <h2 className="mb-4 text-base font-semibold">Add Category</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="e.g. Groceries"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                autoFocus
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Icon (emoji)</label>
              <input
                type="text"
                value={icon}
                onChange={(e) => setIcon(e.target.value)}
                required
                placeholder="e.g. 🛒"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={!name.trim() || !icon.trim() || createCategory.isPending}
              className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            >
              {createCategory.isPending ? 'Saving…' : 'Add Category'}
            </button>
          </form>
        </SheetContent>
      </SheetPortal>
    </Sheet>
  )
}

function AddRuleSheet({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const { data: categories } = useCategories()
  const createRule = useCreateRule()
  const [pattern, setPattern] = useState('')
  const [categoryId, setCategoryId] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!pattern.trim() || !categoryId) return
    createRule.mutate(
      { pattern: pattern.trim(), category_id: categoryId },
      {
        onSuccess: () => {
          setPattern('')
          setCategoryId('')
          onOpenChange(false)
        },
      }
    )
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetPortal>
        <SheetOverlay />
        <SheetContent side="bottom" className="rounded-t-2xl px-4 pb-8 pt-4">
          <div className="mb-4 h-1 w-10 rounded-full bg-muted mx-auto" />
          <h2 className="mb-4 text-base font-semibold">Add Auto-tagging Rule</h2>
          <p className="mb-4 text-xs text-muted-foreground">
            When a transaction description contains this text, it will automatically be tagged with the chosen category.
          </p>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Pattern (text to match)</label>
              <input
                type="text"
                value={pattern}
                onChange={(e) => setPattern(e.target.value)}
                required
                placeholder="e.g. SWIGGY"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono"
                autoFocus
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Category</label>
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                required
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              >
                <option value="">Select category…</option>
                {(categories ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.icon} {c.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              disabled={!pattern.trim() || !categoryId || createRule.isPending}
              className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            >
              {createRule.isPending ? 'Saving…' : 'Add Rule'}
            </button>
          </form>
        </SheetContent>
      </SheetPortal>
    </Sheet>
  )
}

export default function CategoriesPage() {
  const navigate = useNavigate()
  const { data: categories, isLoading: loadingCats } = useCategories()
  const { data: rules, isLoading: loadingRules } = useRules()
  const [addCatOpen, setAddCatOpen] = useState(false)
  const [addRuleOpen, setAddRuleOpen] = useState(false)

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
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Categories
            </h2>
            <button
              onClick={() => setAddCatOpen(true)}
              className="flex items-center gap-0.5 text-xs text-primary font-medium"
              aria-label="Add category"
            >
              <Plus className="h-3.5 w-3.5" /> Add
            </button>
          </div>
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
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Auto-tagging Rules
            </h2>
            <button
              onClick={() => setAddRuleOpen(true)}
              className="flex items-center gap-0.5 text-xs text-primary font-medium"
              aria-label="Add rule"
            >
              <Plus className="h-3.5 w-3.5" /> Add
            </button>
          </div>
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

      <AddCategorySheet open={addCatOpen} onOpenChange={setAddCatOpen} />
      <AddRuleSheet open={addRuleOpen} onOpenChange={setAddRuleOpen} />
    </div>
  )
}
