import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'
import { cn } from '@/lib/utils'

const PLACEHOLDER = [
  { id: '1', name: 'Arjun S.', net_balance_paise: 50000 },
  { id: '2', name: 'Priya M.', net_balance_paise: -120000 },
  { id: '3', name: 'Ravi K.', net_balance_paise: 35000 },
]

export function PeerBalancesWidget() {
  const navigate = useNavigate()

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle>Peer Balances</CardTitle>
        <button onClick={() => navigate('/peers')} className="text-xs text-primary">
          See all
        </button>
      </CardHeader>
      <CardContent className="space-y-3">
        {PLACEHOLDER.map((peer) => {
          const owesYou = peer.net_balance_paise > 0
          return (
            <div key={peer.id} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-sm font-semibold">
                  {peer.name[0]}
                </div>
                <span className="text-sm font-medium">{peer.name}</span>
              </div>
              <div className="text-right">
                <div className={cn('text-sm font-semibold', owesYou ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground')}>
                  {owesYou ? '+' : '−'}{formatCompactINR(Math.abs(peer.net_balance_paise))}
                </div>
                <div className="text-xs text-muted-foreground">
                  {owesYou ? 'owes you' : 'you owe'}
                </div>
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
