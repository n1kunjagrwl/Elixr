import { useRef, useState } from 'react'
import { Sheet, SheetContent, SheetPortal, SheetOverlay } from '@/components/ui/sheet'
import { useAccounts, useUploadStatement } from '@/hooks/useAccounts'

interface Props {
  open: boolean
  onOpenChange: (v: boolean) => void
}

export function UploadStatementSheet({ open, onOpenChange }: Props) {
  const { data: accounts } = useAccounts()
  const upload = useUploadStatement()
  const fileRef = useRef<HTMLInputElement>(null)
  const [accountId, setAccountId] = useState('')
  const [fileName, setFileName] = useState('')
  const [done, setDone] = useState(false)

  const activeAccounts = (accounts ?? []).filter((a) => a.is_active)

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    setFileName(f?.name ?? '')
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file || !accountId) return
    upload.mutate(
      { accountId, file },
      {
        onSuccess: () => {
          setDone(true)
          setTimeout(() => {
            setDone(false)
            setAccountId('')
            setFileName('')
            if (fileRef.current) fileRef.current.value = ''
            onOpenChange(false)
          }, 1500)
        },
      }
    )
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetPortal>
        <SheetOverlay />
        <SheetContent side="bottom" className="rounded-t-2xl px-4 pb-8 pt-4">
          <div className="mb-4 h-1 w-10 rounded-full bg-muted mx-auto" />
          <h2 className="mb-4 text-base font-semibold">Upload Statement</h2>
          {done ? (
            <p className="py-6 text-center text-sm text-green-600">Statement uploaded — processing will begin shortly.</p>
          ) : activeAccounts.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Add an account first before uploading a statement.</p>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Account</label>
                <select
                  value={accountId}
                  onChange={(e) => setAccountId(e.target.value)}
                  required
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select account…</option>
                  {activeAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.label} (••••{a.last4})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Statement file (PDF or CSV)</label>
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  className="w-full rounded-lg border border-dashed px-3 py-4 text-center text-sm text-muted-foreground hover:bg-muted/50"
                >
                  {fileName ? fileName : 'Tap to choose file…'}
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.csv"
                  className="hidden"
                  onChange={handleFile}
                />
              </div>
              <button
                type="submit"
                disabled={!accountId || !fileName || upload.isPending}
                className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
              >
                {upload.isPending ? 'Uploading…' : 'Upload'}
              </button>
            </form>
          )}
        </SheetContent>
      </SheetPortal>
    </Sheet>
  )
}
