import { useState } from 'react'
import { format } from 'date-fns'
import { Sheet, SheetContent, SheetPortal, SheetOverlay } from '@/components/ui/sheet'
import { useAccounts } from '@/hooks/useAccounts'
import { useCategories } from '@/hooks/useCategories'
import { useCreateTransaction } from '@/hooks/useTransactions'

interface Props {
  open: boolean
  onOpenChange: (v: boolean) => void
}

export function AddTransactionSheet({ open, onOpenChange }: Props) {
  const { data: accounts } = useAccounts()
  const { data: categories } = useCategories()
  const create = useCreateTransaction()

  const [accountId, setAccountId] = useState('')
  const [type, setType] = useState<'debit' | 'credit'>('debit')
  const [amount, setAmount] = useState('')
  const [date, setDate] = useState(format(new Date(), 'yyyy-MM-dd'))
  const [description, setDescription] = useState('')
  const [categoryId, setCategoryId] = useState('')

  const activeAccounts = (accounts ?? []).filter((a) => a.is_active)
  const expenseCategories = (categories ?? []).filter((c) => !c.is_system || type === 'credit')

  function reset() {
    setAccountId('')
    setType('debit')
    setAmount('')
    setDate(format(new Date(), 'yyyy-MM-dd'))
    setDescription('')
    setCategoryId('')
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const account = activeAccounts.find((a) => a.id === accountId)
    if (!account || !amount || !categoryId) return

    const amountNum = parseFloat(amount)
    if (isNaN(amountNum) || amountNum <= 0) return

    const account_kind = account.type === 'credit_card' ? 'credit_card' : 'bank_account'

    create.mutate(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      {
        account_id: accountId,
        account_kind,
        type,
        amount: amountNum,
        date,
        raw_description: description || undefined,
        items: [{ category_id: categoryId, amount: amountNum }],
      } as any,
      {
        onSuccess: () => {
          reset()
          onOpenChange(false)
        },
      }
    )
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetPortal>
        <SheetOverlay />
        <SheetContent side="bottom" className="rounded-t-2xl px-4 pb-8 pt-4 max-h-[90vh] overflow-y-auto">
          <div className="mb-4 h-1 w-10 rounded-full bg-muted mx-auto" />
          <h2 className="mb-4 text-base font-semibold">Add Transaction</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Type toggle */}
            <div className="flex gap-2">
              {(['debit', 'credit'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setType(t)}
                  className={`flex-1 rounded-lg border py-2 text-sm font-medium capitalize transition-colors ${
                    type === t ? 'border-primary bg-primary text-primary-foreground' : 'border-border'
                  }`}
                >
                  {t === 'debit' ? 'Expense' : 'Income'}
                </button>
              ))}
            </div>

            {/* Amount */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Amount (₹)</label>
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
                placeholder="0.00"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>

            {/* Account */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Account</label>
              <select
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                required
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              >
                <option value="">Select account…</option>
                {activeAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label} (••••{a.last4})
                  </option>
                ))}
              </select>
            </div>

            {/* Category */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Category</label>
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                required
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              >
                <option value="">Select category…</option>
                {expenseCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.icon} {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Date */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Date</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>

            {/* Description */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Description (optional)</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Coffee at Starbucks"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>

            <button
              type="submit"
              disabled={!accountId || !amount || !categoryId || create.isPending}
              className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            >
              {create.isPending ? 'Saving…' : 'Save Transaction'}
            </button>
          </form>
        </SheetContent>
      </SheetPortal>
    </Sheet>
  )
}
