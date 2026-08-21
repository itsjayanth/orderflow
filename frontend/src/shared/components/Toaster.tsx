import { CheckCircle2, XCircle } from 'lucide-react'
import { useEffect } from 'react'

import { cn } from '@/lib/utils'
import { useToastStore } from '@/shared/lib/toastStore'

const AUTO_DISMISS_MS = 3200

function ToastItem({
  id,
  message,
  tone,
}: {
  id: number
  message: string
  tone: 'success' | 'error'
}) {
  const dismiss = useToastStore((state) => state.dismiss)

  useEffect(() => {
    const timer = setTimeout(() => dismiss(id), AUTO_DISMISS_MS)
    return () => clearTimeout(timer)
  }, [id, dismiss])

  const Icon = tone === 'success' ? CheckCircle2 : XCircle

  return (
    <div
      role="status"
      className={cn(
        'animate-in slide-in-from-bottom-2 fade-in bg-card flex items-center gap-2.5 rounded-xl border px-4 py-3 text-sm font-medium shadow-lg duration-200',
        tone === 'success' ? 'text-foreground' : 'text-destructive',
      )}
    >
      <Icon
        className={cn('size-4 shrink-0', tone === 'success' ? 'text-primary' : 'text-destructive')}
      />
      {message}
    </div>
  )
}

// Mounted once in Layout.tsx -- every useMutation onSuccess/onError across
// the dashboard pushes into the same store rather than each page owning
// its own inline "Saved!" text, so a save anywhere in the app gets the
// same premium, consistent confirmation.
export function Toaster() {
  const toasts = useToastStore((state) => state.toasts)

  if (toasts.length === 0) return null

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:items-end sm:pr-6">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <ToastItem {...t} />
        </div>
      ))}
    </div>
  )
}
