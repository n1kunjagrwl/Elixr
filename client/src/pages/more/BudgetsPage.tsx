import { ChevronLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function BudgetsPage() {
  const navigate = useNavigate()
  return (
    <div>
      <header className="flex items-center gap-2 px-2 py-3 pt-safe">
        <button onClick={() => navigate('/more')} className="p-2 text-muted-foreground">
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h1 className="text-lg font-semibold">Budgets</h1>
      </header>
      <div className="flex flex-col items-center justify-center gap-2 px-8 py-16 text-center text-muted-foreground">
        <p className="text-sm">No budgets set yet.</p>
        <p className="text-xs">Tap + to create your first budget.</p>
      </div>
    </div>
  )
}
