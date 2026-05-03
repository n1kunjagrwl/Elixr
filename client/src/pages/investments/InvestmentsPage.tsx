import { TrendingUp, TrendingDown } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Card, CardContent } from '@/components/ui/card'
import { formatCompactINR, formatDate } from '@/lib/format'
import { cn } from '@/lib/utils'
import { usePortfolioSummary, useHoldings, useSips, useFds } from '@/hooks/useInvestments'

const TYPE_LABELS: Record<string, string> = {
  mutual_fund: 'Mutual Fund',
  stock: 'Stock',
  crypto: 'Crypto',
  gold: 'Gold',
  fd: 'FD',
  other: 'Other',
}

function SkeletonCard() {
  return (
    <Card>
      <CardContent className="pt-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1.5 flex-1">
            <div className="h-4 w-40 animate-pulse rounded bg-muted" />
            <div className="h-3 w-24 animate-pulse rounded bg-muted" />
          </div>
          <div className="space-y-1.5 text-right shrink-0">
            <div className="h-4 w-16 animate-pulse rounded bg-muted ml-auto" />
            <div className="h-3 w-10 animate-pulse rounded bg-muted ml-auto" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="py-10 text-center text-sm text-muted-foreground" data-testid="empty-state">
      {message}
    </div>
  )
}

export default function InvestmentsPage() {
  const { data: summary, isLoading: summaryLoading } = usePortfolioSummary()
  const { data: holdings, isLoading: holdingsLoading } = useHoldings()
  const { data: sips, isLoading: sipsLoading } = useSips()
  const { data: fds, isLoading: fdsLoading } = useFds()

  const totalValuePaise = summary?.total_value_paise ?? 0
  const pnlPaise = summary?.pnl_paise ?? 0
  const pnlPercent = summary?.pnl_percent ?? 0
  const isPositive = pnlPaise >= 0

  return (
    <div>
      <Header title="Investments" />

      <div className="px-4 pb-4">
        {/* Portfolio summary card */}
        <Card className="mb-4">
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
              Portfolio Value
            </div>
            {summaryLoading && !summary ? (
              <div className="mt-1 space-y-1.5">
                <div className="h-8 w-32 animate-pulse rounded bg-muted" />
                <div className="h-4 w-24 animate-pulse rounded bg-muted" />
              </div>
            ) : (
              <>
                <div className="text-3xl font-bold mt-1" data-testid="portfolio-value">
                  {formatCompactINR(totalValuePaise)}
                </div>
                {pnlPaise !== 0 && (
                  <div
                    className={cn(
                      'flex items-center gap-1 text-sm mt-1',
                      isPositive ? 'text-green-600 dark:text-green-400' : 'text-destructive'
                    )}
                    data-testid="portfolio-pnl"
                  >
                    {isPositive ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <TrendingDown className="h-4 w-4" />
                    )}
                    <span>
                      {isPositive ? '+' : ''}
                      {formatCompactINR(pnlPaise)} ({pnlPercent.toFixed(1)}%) overall
                    </span>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <Tabs defaultValue="holdings" className="w-full">
          <TabsList className="w-full grid grid-cols-3">
            <TabsTrigger value="holdings">Holdings</TabsTrigger>
            <TabsTrigger value="sips">SIPs</TabsTrigger>
            <TabsTrigger value="fds">FDs</TabsTrigger>
          </TabsList>

          {/* Holdings tab */}
          <TabsContent value="holdings" className="space-y-3">
            {holdingsLoading && !holdings ? (
              Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
            ) : (holdings ?? []).length === 0 ? (
              <EmptyState message="No holdings added" />
            ) : (
              (holdings ?? []).map((h) => (
                <Card key={h.id} data-testid={`holding-row-${h.id}`}>
                  <CardContent className="pt-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="font-medium text-sm truncate">{h.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {TYPE_LABELS[h.type] ?? h.type} · {h.units} units
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="font-semibold text-sm">
                          {formatCompactINR(h.current_value_paise)}
                        </div>
                        <div
                          className={cn(
                            'text-xs',
                            h.pnl_paise >= 0
                              ? 'text-green-600 dark:text-green-400'
                              : 'text-destructive'
                          )}
                        >
                          {h.pnl_paise >= 0 ? '+' : ''}
                          {h.pnl_percent.toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </TabsContent>

          {/* SIPs tab */}
          <TabsContent value="sips" className="space-y-3">
            {sipsLoading && !sips ? (
              Array.from({ length: 2 }).map((_, i) => <SkeletonCard key={i} />)
            ) : (sips ?? []).length === 0 ? (
              <EmptyState message="No active SIPs" />
            ) : (
              (sips ?? []).map((sip) => (
                <Card key={sip.id} data-testid={`sip-row-${sip.id}`}>
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-sm">{sip.name}</div>
                        <div className="text-xs text-muted-foreground">
                          Next: {formatDate(sip.next_date)}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold text-sm">
                          {formatCompactINR(sip.amount_paise)}/mo
                        </div>
                        <div className="text-xs text-green-600 dark:text-green-400 capitalize">
                          {sip.status}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </TabsContent>

          {/* FDs tab */}
          <TabsContent value="fds" className="space-y-3">
            {fdsLoading && !fds ? (
              Array.from({ length: 2 }).map((_, i) => <SkeletonCard key={i} />)
            ) : (fds ?? []).length === 0 ? (
              <EmptyState message="No fixed deposits" />
            ) : (
              (fds ?? []).map((fd) => (
                <Card key={fd.id} data-testid={`fd-row-${fd.id}`}>
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-sm">{fd.bank} FD</div>
                        <div className="text-xs text-muted-foreground">
                          {fd.rate}% · Matures {formatDate(fd.maturity_date)}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold text-sm">
                          {formatCompactINR(fd.maturity_paise)}
                        </div>
                        <div className="text-xs text-muted-foreground">at maturity</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
