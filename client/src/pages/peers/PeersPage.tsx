import { UserPlus } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { Card, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'
import { cn } from '@/lib/utils'

const PEERS = [
  { id: '1', name: 'Arjun Sharma', initials: 'AS', net_balance_paise: 50000 },
  { id: '2', name: 'Priya Mehta', initials: 'PM', net_balance_paise: -120000 },
  { id: '3', name: 'Ravi Kumar', initials: 'RK', net_balance_paise: 35000 },
  { id: '4', name: 'Sneha Patel', initials: 'SP', net_balance_paise: 0 },
]

const totalOwedToYou = PEERS.filter((p) => p.net_balance_paise > 0).reduce((s, p) => s + p.net_balance_paise, 0)
const totalYouOwe = PEERS.filter((p) => p.net_balance_paise < 0).reduce((s, p) => s + Math.abs(p.net_balance_paise), 0)

export default function PeersPage() {
  return (
    <div>
      <Header
        title="Peers"
        action={
          <button className="flex items-center gap-1 text-sm text-primary font-medium">
            <UserPlus className="h-4 w-4" /> Add
          </button>
        }
      />

      <div className="px-4 space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Card>
            <CardContent className="pt-4">
              <div className="text-xs text-muted-foreground font-medium">Owed to you</div>
              <div className="text-xl font-bold text-green-600 dark:text-green-400 mt-1">
                {formatCompactINR(totalOwedToYou)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-xs text-muted-foreground font-medium">You owe</div>
              <div className="text-xl font-bold mt-1">{formatCompactINR(totalYouOwe)}</div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-2">
          {PEERS.map((peer) => {
            const owesYou = peer.net_balance_paise > 0
            const settled = peer.net_balance_paise === 0
            return (
              <Card key={peer.id}>
                <CardContent className="flex items-center gap-3 py-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-bold">
                    {peer.initials}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm">{peer.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {settled ? 'All settled' : owesYou ? 'Owes you' : 'You owe'}
                    </div>
                  </div>
                  {!settled && (
                    <div className="text-right">
                      <div className={cn('text-sm font-semibold', owesYou ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground')}>
                        {owesYou ? '+' : '−'}{formatCompactINR(Math.abs(peer.net_balance_paise))}
                      </div>
                      <button className="text-xs text-primary">Settle</button>
                    </div>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>
    </div>
  )
}
