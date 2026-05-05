import { ChevronLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { useThemeStore } from '@/store/theme'
import { useDashboardStore } from '@/store/dashboard'
import type { Theme, AccentColor } from '@/types'

const THEMES: { value: Theme; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
]

const ACCENTS: { value: AccentColor; label: string; oklch: string }[] = [
  { value: 'teal', label: 'Teal', oklch: '0.67 0.13 200' },
  { value: 'blue', label: 'Blue', oklch: '0.6 0.19 250' },
  { value: 'purple', label: 'Purple', oklch: '0.6 0.18 290' },
  { value: 'orange', label: 'Orange', oklch: '0.72 0.19 45' },
  { value: 'green', label: 'Green', oklch: '0.65 0.16 150' },
]

export default function SettingsPage() {
  const navigate = useNavigate()
  const { theme, accent, setTheme, setAccent } = useThemeStore()
  const { widgets, toggleWidget } = useDashboardStore()

  return (
    <div>
      <header className="flex items-center gap-2 px-2 py-3 pt-safe">
        <button
          onClick={() => navigate('/more')}
          className="p-2 text-muted-foreground"
          aria-label="Back"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h1 className="text-lg font-semibold">Settings</h1>
      </header>

      <div className="px-4 space-y-5">
        {/* Appearance */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Appearance
          </h2>
          <Card>
            <CardContent className="py-3 space-y-4">
              {/* Theme */}
              <div>
                <div className="mb-2 text-sm font-medium">Theme</div>
                <div className="flex gap-2" data-testid="theme-selector">
                  {THEMES.map(({ value, label }) => (
                    <button
                      key={value}
                      onClick={() => setTheme(value)}
                      data-testid={`theme-${value}`}
                      className={cn(
                        'flex-1 rounded-lg border px-3 py-2 text-xs font-medium transition-colors',
                        theme === value
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border bg-background text-foreground hover:bg-muted'
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Accent color */}
              <div>
                <div className="mb-2 text-sm font-medium">Accent Color</div>
                <div className="flex gap-2" data-testid="accent-selector">
                  {ACCENTS.map(({ value, label, oklch }) => (
                    <button
                      key={value}
                      onClick={() => setAccent(value)}
                      data-testid={`accent-${value}`}
                      aria-label={label}
                      className={cn(
                        'h-7 w-7 rounded-full border-2 transition-all',
                        accent === value ? 'border-foreground scale-110' : 'border-transparent'
                      )}
                      style={{ background: `oklch(${oklch})` }}
                    />
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Dashboard widgets */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Dashboard Widgets
          </h2>
          <Card>
            <CardContent className="py-1">
              {widgets
                .slice()
                .sort((a, b) => a.order - b.order)
                .map((widget) => (
                  <div
                    key={widget.id}
                    className="flex items-center justify-between py-2.5 border-b last:border-0"
                    data-testid={`widget-toggle-${widget.id}`}
                  >
                    <span className="text-sm">{widget.label}</span>
                    <button
                      onClick={() => toggleWidget(widget.id)}
                      aria-pressed={widget.visible}
                      className={cn(
                        'relative h-5 w-9 rounded-full transition-colors',
                        widget.visible ? 'bg-primary' : 'bg-muted'
                      )}
                    >
                      <span
                        className={cn(
                          'absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform',
                          widget.visible ? 'left-4' : 'left-0.5'
                        )}
                      />
                    </button>
                  </div>
                ))}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}
