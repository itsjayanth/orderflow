import { X } from 'lucide-react'
import type * as React from 'react'
import { useEffect } from 'react'

interface SheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  children: React.ReactNode
  footer?: React.ReactNode
}

// Hand-rolled instead of a Radix Dialog primitive -- this repo doesn't
// depend on @radix-ui/react-dialog yet, and a bottom sheet with a
// backdrop + Escape-to-close + scroll lock doesn't need much more than
// that to be usable and accessible.
export function Sheet({ open, onOpenChange, title, children, footer }: SheetProps) {
  useEffect(() => {
    if (!open) {
      return
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onOpenChange(false)
      }
    }
    document.addEventListener('keydown', onKeyDown)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [open, onOpenChange])

  if (!open) {
    return null
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center sm:items-center">
      <button
        type="button"
        aria-label="Close"
        className="animate-in fade-in absolute inset-0 bg-black/40 backdrop-blur-[1px] duration-200"
        onClick={() => onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="animate-in slide-in-from-bottom sm:zoom-in-95 bg-card relative z-10 flex max-h-[85svh] w-full max-w-md flex-col rounded-t-2xl border shadow-2xl duration-200 sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="font-serif text-lg font-semibold">{title}</h2>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Close"
            className="text-muted-foreground hover:bg-accent hover:text-accent-foreground rounded-full p-1.5 transition-colors duration-150"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="space-y-2 border-t px-5 py-4">{footer}</div>}
      </div>
    </div>
  )
}
