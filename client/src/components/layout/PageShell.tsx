import { Outlet } from 'react-router-dom'
import { BottomNav } from './BottomNav'
import { FAB } from './FAB'

export function PageShell() {
  return (
    <div className="flex h-dvh flex-col bg-background">
      <main className="flex-1 overflow-y-auto pb-20">
        <Outlet />
      </main>
      <FAB />
      <BottomNav />
    </div>
  )
}
