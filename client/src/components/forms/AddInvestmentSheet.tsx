import { useState } from 'react'
import { Sheet, SheetContent, SheetPortal, SheetOverlay } from '@/components/ui/sheet'
import { useAddHolding } from '@/hooks/useInvestments'

interface Props {
  open: boolean
  onOpenChange: (v: boolean) => void
}

const TYPES = [
  { value: 'mutual_fund', label: 'Mutual Fund' },
  { value: 'stock', label: 'Stock' },
  { value: 'crypto', label: 'Crypto' },
  { value: 'gold', label: 'Gold' },
  { value: 'other', label: 'Other' },
] as const

type InstrumentType = typeof TYPES[number]['value']

export function AddInvestmentSheet({ open, onOpenChange }: Props) {
  const add = useAddHolding()

  const [name, setName] = useState('')
  const [type, setType] = useState<InstrumentType>('mutual_fund')
  const [units, setUnits] = useState('')
  const [avgCost, setAvgCost] = useState('')
  const [currentValue, setCurrentValue] = useState('')

  function reset() {
    setName('')
    setType('mutual_fund')
    setUnits('')
    setAvgCost('')
    setCurrentValue('')
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name) return

    add.mutate(
      {
        name,
        type,
        units: units ? parseFloat(units) : undefined,
        avg_cost_per_unit: avgCost ? parseFloat(avgCost) : undefined,
        current_value: currentValue ? parseFloat(currentValue) : undefined,
      },
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
          <h2 className="mb-4 text-base font-semibold">Add Investment</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="e.g. Nifty 50 Index Fund"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>

            {/* Type */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Type</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as InstrumentType)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              >
                {TYPES.map(({ value, label }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>

            {/* Units */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Units (optional)</label>
              <input
                type="number"
                min="0"
                step="any"
                value={units}
                onChange={(e) => setUnits(e.target.value)}
                placeholder="e.g. 100"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>

            {/* Avg cost */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Avg cost per unit ₹ (optional)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={avgCost}
                onChange={(e) => setAvgCost(e.target.value)}
                placeholder="e.g. 150.50"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>

            {/* Current value */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Current value ₹ (optional)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={currentValue}
                onChange={(e) => setCurrentValue(e.target.value)}
                placeholder="e.g. 18500"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
            </div>

            <button
              type="submit"
              disabled={!name || add.isPending}
              className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            >
              {add.isPending ? 'Saving…' : 'Add Investment'}
            </button>
          </form>
        </SheetContent>
      </SheetPortal>
    </Sheet>
  )
}
