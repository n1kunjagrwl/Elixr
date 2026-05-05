import { useState } from 'react'
import { ChevronLeft, CreditCard, Building2, Plus } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { Sheet, SheetContent, SheetPortal, SheetOverlay } from '@/components/ui/sheet'
import { useAccounts, useCreateBankAccount, useCreateCreditCard } from '@/hooks/useAccounts'

function AccountSkeleton() {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-3">
        <div className="h-9 w-9 shrink-0 animate-pulse rounded-lg bg-muted" />
        <div className="flex-1 space-y-1.5">
          <div className="h-3.5 w-32 animate-pulse rounded bg-muted" />
          <div className="h-3 w-20 animate-pulse rounded bg-muted" />
        </div>
        <div className="h-3 w-16 animate-pulse rounded bg-muted" />
      </CardContent>
    </Card>
  )
}

const TYPE_LABEL: Record<string, string> = {
  bank: 'Bank Account',
  credit_card: 'Credit Card',
}

function AddAccountSheet({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const createBank = useCreateBankAccount()
  const createCard = useCreateCreditCard()
  const [accountType, setAccountType] = useState<'bank' | 'credit_card'>('bank')
  const [nickname, setNickname] = useState('')
  const [bankName, setBankName] = useState('')
  const [last4, setLast4] = useState('')
  const [bankSubtype, setBankSubtype] = useState<'savings' | 'current' | 'salary'>('savings')

  const isPending = createBank.isPending || createCard.isPending

  function reset() {
    setNickname('')
    setBankName('')
    setLast4('')
    setBankSubtype('savings')
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!nickname.trim() || !bankName.trim()) return

    const onSuccess = () => { reset(); onOpenChange(false) }

    if (accountType === 'bank') {
      createBank.mutate(
        {
          nickname: nickname.trim(),
          bank_name: bankName.trim(),
          account_type: bankSubtype,
          last4: last4 || undefined,
        },
        { onSuccess }
      )
    } else {
      createCard.mutate(
        {
          nickname: nickname.trim(),
          bank_name: bankName.trim(),
          last4: last4 || undefined,
        },
        { onSuccess }
      )
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetPortal>
        <SheetOverlay />
        <SheetContent side="bottom" className="rounded-t-2xl px-4 pb-8 pt-4 max-h-[90vh] overflow-y-auto">
          <div className="mb-4 h-1 w-10 rounded-full bg-muted mx-auto" />
          <h2 className="mb-4 text-base font-semibold">Add Account</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Account type toggle */}
            <div className="flex gap-2">
              {(['bank', 'credit_card'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setAccountType(t)}
                  className={`flex-1 rounded-lg border py-2 text-sm font-medium transition-colors ${
                    accountType === t
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border'
                  }`}
                >
                  {t === 'bank' ? 'Bank Account' : 'Credit Card'}
                </button>
              ))}
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Nickname</label>
              <input
                type="text"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                required
                placeholder="e.g. HDFC Savings"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                autoFocus
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Bank name</label>
              <input
                type="text"
                value={bankName}
                onChange={(e) => setBankName(e.target.value)}
                required
                placeholder="e.g. HDFC Bank"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>

            {accountType === 'bank' && (
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Account type</label>
                <select
                  value={bankSubtype}
                  onChange={(e) => setBankSubtype(e.target.value as typeof bankSubtype)}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                >
                  <option value="savings">Savings</option>
                  <option value="current">Current</option>
                  <option value="salary">Salary</option>
                </select>
              </div>
            )}

            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Last 4 digits (optional)
              </label>
              <input
                type="text"
                value={last4}
                onChange={(e) => setLast4(e.target.value.replace(/\D/g, '').slice(0, 4))}
                maxLength={4}
                placeholder="e.g. 1234"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>

            <button
              type="submit"
              disabled={!nickname.trim() || !bankName.trim() || isPending}
              className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            >
              {isPending ? 'Saving…' : 'Add Account'}
            </button>
          </form>
        </SheetContent>
      </SheetPortal>
    </Sheet>
  )
}

export default function AccountsPage() {
  const navigate = useNavigate()
  const { data: accounts, isLoading } = useAccounts()
  const [addOpen, setAddOpen] = useState(false)

  return (
    <div>
      <header className="flex items-center justify-between px-2 py-3 pt-safe">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/more')}
            className="p-2 text-muted-foreground"
            aria-label="Back"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-semibold">Accounts</h1>
        </div>
        <button
          onClick={() => setAddOpen(true)}
          className="flex items-center gap-1 p-2 text-primary"
          aria-label="Add account"
        >
          <Plus className="h-5 w-5" />
        </button>
      </header>

      <div className="px-4 space-y-2">
        {isLoading && !accounts ? (
          Array.from({ length: 2 }).map((_, i) => <AccountSkeleton key={i} />)
        ) : (accounts ?? []).length === 0 ? (
          <div
            className="flex flex-col items-center justify-center gap-2 py-16 text-center text-muted-foreground"
            data-testid="empty-state"
          >
            <p className="text-sm">No accounts linked yet.</p>
            <p className="text-xs">Add bank accounts or credit cards to get started.</p>
          </div>
        ) : (
          (accounts ?? []).map((account) => {
            const Icon = account.type === 'credit_card' ? CreditCard : Building2
            return (
              <Card key={account.id} data-testid={`account-row-${account.id}`}>
                <CardContent className="flex items-center gap-3 py-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <Icon className="h-4.5 w-4.5 text-foreground" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{account.label}</div>
                    <div className="text-xs text-muted-foreground">
                      {account.bank_name} · {TYPE_LABEL[account.type] ?? account.type}
                    </div>
                  </div>
                  <div className="text-xs font-mono text-muted-foreground">••••{account.last4}</div>
                </CardContent>
              </Card>
            )
          })
        )}
      </div>

      <AddAccountSheet open={addOpen} onOpenChange={setAddOpen} />
    </div>
  )
}
