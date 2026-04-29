import { useState, useRef, useEffect } from 'react'
import { Plus, Upload, PenLine, TrendingUp, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'

const actions = [
  { icon: Upload, label: 'Upload Statement', color: 'bg-blue-500' },
  { icon: PenLine, label: 'Add Transaction', color: 'bg-green-500' },
  { icon: TrendingUp, label: 'Add Investment', color: 'bg-purple-500' },
]

export function FAB() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  return (
    <div ref={ref} className="fixed bottom-20 right-4 z-50 flex flex-col-reverse items-end gap-2">
      <AnimatePresence>
        {open &&
          actions.map(({ icon: Icon, label, color }, i) => (
            <motion.button
              key={label}
              initial={{ opacity: 0, y: 8, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.9 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-full bg-background px-3 py-2 shadow-lg border"
              aria-label={label}
            >
              <span className={cn('flex h-8 w-8 items-center justify-center rounded-full text-white', color)}>
                <Icon className="h-4 w-4" />
              </span>
              <span className="text-sm font-medium pr-1">{label}</span>
            </motion.button>
          ))}
      </AnimatePresence>

      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition-all',
          open ? 'bg-foreground text-background' : 'bg-primary text-primary-foreground'
        )}
        aria-label="Quick actions"
      >
        <motion.div animate={{ rotate: open ? 45 : 0 }} transition={{ duration: 0.2 }}>
          {open ? <X className="h-6 w-6" /> : <Plus className="h-6 w-6" />}
        </motion.div>
      </button>
    </div>
  )
}
