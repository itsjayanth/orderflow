import { create } from 'zustand'

type ToastTone = 'success' | 'error'

interface Toast {
  id: number
  message: string
  tone: ToastTone
}

interface ToastState {
  toasts: Toast[]
  push: (message: string, tone: ToastTone) => void
  dismiss: (id: number) => void
}

let nextId = 1

// Hand-rolled instead of a toast library (e.g. sonner) -- same call this
// repo already made for Sheet (components/ui/sheet.tsx): a global
// auto-dismissing message queue doesn't need much more than a tiny
// Zustand store + a fixed-position renderer (shared/components/Toaster.tsx).
export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (message, tone) =>
    set((state) => ({ toasts: [...state.toasts, { id: nextId++, message, tone }] })),
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}))

interface ToastFn {
  (message: string): void
  error: (message: string) => void
}

export const toast = ((message: string) => {
  useToastStore.getState().push(message, 'success')
}) as ToastFn

toast.error = (message: string) => {
  useToastStore.getState().push(message, 'error')
}
