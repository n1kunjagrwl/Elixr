import { ChevronLeft, CreditCard, Building2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { useAccounts } from '@/hooks/useAccounts'

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

export default function AccountsPage() {
  const navigate = useNavigate()
  const { data: accounts, isLoading } = useAccounts()

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
        <h1 className="text-lg font-semibold">Accounts</h1>
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
    </div>
  )
}
