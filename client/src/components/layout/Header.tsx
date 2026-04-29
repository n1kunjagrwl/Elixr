import { cn } from '@/lib/utils'

interface HeaderProps {
  title: string
  action?: React.ReactNode
  className?: string
}

export function Header({ title, action, className }: HeaderProps) {
  return (
    <header className={cn('flex items-center justify-between px-4 py-3 pt-safe', className)}>
      <h1 className="text-lg font-semibold">{title}</h1>
      {action && <div>{action}</div>}
    </header>
  )
}
