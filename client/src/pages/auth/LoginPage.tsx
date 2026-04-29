import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { requestOtp, verifyOtp } from '@/api/identity'
import { useAuthStore } from '@/store/auth'
import { cn } from '@/lib/utils'

type Step = 'phone' | 'otp'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setToken } = useAuthStore()

  const [step, setStep] = useState<Step>('phone')
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleRequestOtp(e: React.FormEvent) {
    e.preventDefault()
    if (phone.replace(/\D/g, '').length !== 10) {
      setError('Enter a valid 10-digit mobile number')
      return
    }
    setError(null)
    setLoading(true)
    try {
      await requestOtp(`+91${phone.replace(/\D/g, '')}`)
      setStep('otp')
    } catch {
      setError('Could not send OTP. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault()
    if (otp.length !== 6) {
      setError('Enter the 6-digit OTP')
      return
    }
    setError(null)
    setLoading(true)
    try {
      const { access_token } = await verifyOtp(`+91${phone.replace(/\D/g, '')}`, otp)
      setToken(access_token)
      navigate('/home', { replace: true })
    } catch {
      setError('Invalid OTP. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-background px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight">Elixir</h1>
          <p className="mt-2 text-sm text-muted-foreground">Your personal finance companion</p>
        </div>

        {step === 'phone' ? (
          <form onSubmit={handleRequestOtp} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium">Mobile Number</label>
              <div className="flex overflow-hidden rounded-lg border bg-background focus-within:ring-2 focus-within:ring-ring">
                <div className="flex items-center border-r bg-muted px-3 text-sm text-muted-foreground">
                  +91
                </div>
                <input
                  type="tel"
                  inputMode="numeric"
                  maxLength={10}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 10))}
                  placeholder="98765 43210"
                  className="flex-1 bg-transparent px-3 py-3 text-sm outline-none placeholder:text-muted-foreground"
                  autoFocus
                />
              </div>
            </div>

            {error && <p className="text-xs text-destructive">{error}</p>}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Sending OTP…' : (
                <>Send OTP <ArrowRight className="h-4 w-4" /></>
              )}
            </Button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium">
                Enter OTP sent to +91 {phone}
              </label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="• • • • • •"
                className={cn(
                  'w-full rounded-lg border bg-background px-4 py-3 text-center text-2xl tracking-[1rem] outline-none',
                  'focus:ring-2 focus:ring-ring placeholder:text-muted-foreground placeholder:tracking-normal placeholder:text-base'
                )}
                autoFocus
              />
            </div>

            {error && <p className="text-xs text-destructive">{error}</p>}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Verifying…' : 'Verify & Sign in'}
            </Button>

            <button
              type="button"
              onClick={() => { setStep('phone'); setOtp(''); setError(null) }}
              className="flex w-full items-center justify-center gap-1 text-sm text-muted-foreground"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Change number
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
