import { TrendingUp, TrendingDown } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Card, CardContent } from '@/components/ui/card'
import { formatCompactINR, formatDate } from '@/lib/format'
import { cn } from '@/lib/utils'

const HOLDINGS = [
  { id: '1', name: 'Mirae Asset Large Cap', type: 'Mutual Fund', units: 245.3, current_value_paise: 8500000, pnl_paise: 1200000, pnl_percent: 16.4 },
  { id: '2', name: 'HDFC Bank', type: 'Stock', units: 50, current_value_paise: 7800000, pnl_paise: 650000, pnl_percent: 9.1 },
  { id: '3', name: 'Sovereign Gold Bond', type: 'Gold', units: 10, current_value_paise: 5500000, pnl_paise: 800000, pnl_percent: 17.0 },
]

const SIPS = [
  { id: '1', name: 'Axis Bluechip Fund', amount_paise: 500000, next_date: '2026-05-01', status: 'active' },
  { id: '2', name: 'Parag Parikh Flexi Cap', amount_paise: 300000, next_date: '2026-05-05', status: 'active' },
]

const FDS = [
  { id: '1', bank: 'SBI', principal_paise: 5000000, rate: 7.1, maturity_date: '2027-04-15', maturity_paise: 5710000 },
]

const totalValue = HOLDINGS.reduce((s, h) => s + h.current_value_paise, 0)
const totalPnl = HOLDINGS.reduce((s, h) => s + h.pnl_paise, 0)

export default function InvestmentsPage() {
  return (
    <div>
      <Header title="Investments" />

      <div className="px-4 pb-4">
        <Card className="mb-4">
          <CardContent className="pt-4">
            <div className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Portfolio Value</div>
            <div className="text-3xl font-bold mt-1">{formatCompactINR(totalValue)}</div>
            <div className={cn('flex items-center gap-1 text-sm mt-1', totalPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-destructive')}>
              {totalPnl >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
              <span>+{formatCompactINR(totalPnl)} overall</span>
            </div>
          </CardContent>
        </Card>

        <Tabs defaultValue="holdings" className="w-full">
          <TabsList className="w-full grid grid-cols-3">
            <TabsTrigger value="holdings">Holdings</TabsTrigger>
            <TabsTrigger value="sips">SIPs</TabsTrigger>
            <TabsTrigger value="fds">FDs</TabsTrigger>
          </TabsList>

          <TabsContent value="holdings" className="space-y-3">
            {HOLDINGS.map((h) => (
              <Card key={h.id}>
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-medium text-sm truncate">{h.name}</div>
                      <div className="text-xs text-muted-foreground">{h.type} · {h.units} units</div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="font-semibold text-sm">{formatCompactINR(h.current_value_paise)}</div>
                      <div className={cn('text-xs', h.pnl_paise >= 0 ? 'text-green-600 dark:text-green-400' : 'text-destructive')}>
                        +{h.pnl_percent.toFixed(1)}%
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </TabsContent>

          <TabsContent value="sips" className="space-y-3">
            {SIPS.map((sip) => (
              <Card key={sip.id}>
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-sm">{sip.name}</div>
                      <div className="text-xs text-muted-foreground">Next: {formatDate(sip.next_date)}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold text-sm">{formatCompactINR(sip.amount_paise)}/mo</div>
                      <div className="text-xs text-green-600 dark:text-green-400 capitalize">{sip.status}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </TabsContent>

          <TabsContent value="fds" className="space-y-3">
            {FDS.map((fd) => (
              <Card key={fd.id}>
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-sm">{fd.bank} FD</div>
                      <div className="text-xs text-muted-foreground">{fd.rate}% · Matures {formatDate(fd.maturity_date)}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold text-sm">{formatCompactINR(fd.maturity_paise)}</div>
                      <div className="text-xs text-muted-foreground">at maturity</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
