import { ChevronRight, Target, Briefcase, CreditCard, Tag, Settings } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Header } from '@/components/layout/Header'
import { Separator } from '@/components/ui/separator'

const SECTIONS = [
  { icon: Target, label: 'Budgets', description: 'Set and track spending limits', to: '/more/budgets' },
  { icon: Briefcase, label: 'Earnings', description: 'Income sources and salary history', to: '/more/earnings' },
  { icon: CreditCard, label: 'Accounts', description: 'Bank accounts and credit cards', to: '/more/accounts' },
  { icon: Tag, label: 'Categories & Rules', description: 'Manage categories and auto-rules', to: '/more/categories' },
  { icon: Settings, label: 'Settings', description: 'Appearance, dashboard, notifications', to: '/more/settings' },
]

export default function MorePage() {
  const navigate = useNavigate()

  return (
    <div>
      <Header title="More" />

      <div className="px-4">
        <div className="rounded-lg border bg-card overflow-hidden">
          {SECTIONS.map((section, i) => {
            const Icon = section.icon
            return (
              <div key={section.to}>
                <button
                  onClick={() => navigate(section.to)}
                  className="flex w-full items-center gap-3 px-4 py-3.5 text-left active:bg-muted"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <Icon className="h-4.5 w-4.5 text-foreground" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{section.label}</div>
                    <div className="text-xs text-muted-foreground">{section.description}</div>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                </button>
                {i < SECTIONS.length - 1 && <Separator className="ml-16" />}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
