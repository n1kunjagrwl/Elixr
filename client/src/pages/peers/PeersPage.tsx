import { UserPlus } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { Card, CardContent } from '@/components/ui/card'
import { formatCompactINR } from '@/lib/format'
import { cn } from '@/lib/utils'
import { usePeers, useRecordSettlement } from '@/hooks/usePeers'

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

function SummarySkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3">
      {[0, 1].map((i) => (
        <Card key={i}>
          <CardContent className="pt-4 space-y-1.5">
            <div className="h-3 w-20 animate-pulse rounded bg-muted" />
            <div className="h-7 w-16 animate-pulse rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function PeerSkeleton() {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-3">
        <div className="h-10 w-10 shrink-0 animate-pulse rounded-full bg-muted" />
        <div className="flex-1 space-y-1.5">
          <div className="h-3.5 w-28 animate-pulse rounded bg-muted" />
          <div className="h-3 w-16 animate-pulse rounded bg-muted" />
        </div>
        <div className="h-3.5 w-14 animate-pulse rounded bg-muted" />
      </CardContent>
    </Card>
  )
}

export default function PeersPage() {
  const { data: peers, isLoading } = usePeers()
  const settle = useRecordSettlement()

  const totalOwedToYou = (peers ?? [])
    .filter((p) => p.net_balance_paise > 0)
    .reduce((s, p) => s + p.net_balance_paise, 0)

  const totalYouOwe = (peers ?? [])
    .filter((p) => p.net_balance_paise < 0)
    .reduce((s, p) => s + Math.abs(p.net_balance_paise), 0)

  return (
    <div>
      <Header
        title="Peers"
        action={
          <button className="flex items-center gap-1 text-sm text-primary font-medium" aria-label="Add peer">
            <UserPlus className="h-4 w-4" /> Add
          </button>
        }
      />

      <div className="px-4 space-y-4">
        {/* Summary cards */}
        {isLoading && !peers ? (
          <SummarySkeleton />
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <Card>
              <CardContent className="pt-4">
                <div className="text-xs text-muted-foreground font-medium">Owed to you</div>
                <div
                  className="text-xl font-bold text-green-600 dark:text-green-400 mt-1"
                  data-testid="owed-to-you"
                >
                  {formatCompactINR(totalOwedToYou)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="text-xs text-muted-foreground font-medium">You owe</div>
                <div className="text-xl font-bold mt-1" data-testid="you-owe">
                  {formatCompactINR(totalYouOwe)}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Peer list */}
        <div className="space-y-2">
          {isLoading && !peers ? (
            Array.from({ length: 3 }).map((_, i) => <PeerSkeleton key={i} />)
          ) : (peers ?? []).length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground" data-testid="empty-state">
              No peers added yet
            </div>
          ) : (
            (peers ?? []).map((peer) => {
              const owesYou = peer.net_balance_paise > 0
              const settled = peer.net_balance_paise === 0
              return (
                <Card key={peer.id} data-testid={`peer-row-${peer.id}`}>
                  <CardContent className="flex items-center gap-3 py-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-bold">
                      {getInitials(peer.name)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-sm">{peer.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {settled ? 'All settled' : owesYou ? 'Owes you' : 'You owe'}
                      </div>
                    </div>
                    {!settled && (
                      <div className="text-right">
                        <div
                          className={cn(
                            'text-sm font-semibold',
                            owesYou
                              ? 'text-green-600 dark:text-green-400'
                              : 'text-muted-foreground'
                          )}
                        >
                          {owesYou ? '+' : '−'}
                          {formatCompactINR(Math.abs(peer.net_balance_paise))}
                        </div>
                        <button
                          className="text-xs text-primary disabled:opacity-50"
                          disabled={settle.isPending}
                          onClick={() =>
                            settle.mutate({
                              peerId: peer.id,
                              amount_paise: Math.abs(peer.net_balance_paise),
                            })
                          }
                        >
                          Settle
                        </button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
