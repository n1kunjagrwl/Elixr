import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'
import { cn } from '@/lib/utils'
import { usePeers } from '@/hooks/usePeers'

function Skeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 animate-pulse rounded-full bg-muted" />
            <div className="h-3.5 w-20 animate-pulse rounded bg-muted" />
          </div>
          <div className="space-y-1">
            <div className="h-3.5 w-16 animate-pulse rounded bg-muted ml-auto" />
            <div className="h-3 w-12 animate-pulse rounded bg-muted ml-auto" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function PeerBalancesWidget() {
  const navigate = useNavigate()
  const { data: peers, isLoading } = usePeers()

  const top = [...(peers ?? [])]
    .sort((a, b) => Math.abs(b.net_balance_paise) - Math.abs(a.net_balance_paise))
    .slice(0, 3)

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle>Peer Balances</CardTitle>
        <button onClick={() => navigate('/peers')} className="text-xs text-primary">
          See all
        </button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && !peers ? (
          <Skeleton />
        ) : top.length === 0 ? (
          <div className="py-4 text-center text-sm text-muted-foreground">No peer balances</div>
        ) : (
          top.map((peer) => {
            const owesYou = peer.net_balance_paise > 0
            return (
              <div key={peer.id} className="flex items-center justify-between" data-testid={`peer-row-${peer.id}`}>
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-sm font-semibold">
                    {peer.name[0]}
                  </div>
                  <span className="text-sm font-medium">{peer.name}</span>
                </div>
                <div className="text-right">
                  <div
                    className={cn(
                      'text-sm font-semibold',
                      owesYou ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'
                    )}
                  >
                    {owesYou ? '+' : '−'}
                    {formatCompactINR(Math.abs(peer.net_balance_paise))}
                  </div>
                  <div className="text-xs text-muted-foreground">{owesYou ? 'owes you' : 'you owe'}</div>
                </div>
              </div>
            )
          })
        )}
      </CardContent>
    </Card>
  )
}
