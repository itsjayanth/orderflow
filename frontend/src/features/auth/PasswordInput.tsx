import { Eye, EyeOff } from 'lucide-react'
import type { ComponentProps } from 'react'
import { useState } from 'react'

import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

// Shared by LoginPage/RegisterPage so both password fields get an identical
// show/hide affordance. Wraps Input rather than reimplementing it -- local
// `visible` state just flips the native `type`, so nothing about
// react-hook-form's `register()` wiring (name/onChange/onBlur/ref) changes.
export function PasswordInput({ className, ...props }: Omit<ComponentProps<typeof Input>, 'type'>) {
  const [visible, setVisible] = useState(false)

  return (
    <div className="relative">
      <Input type={visible ? 'text' : 'password'} className={cn('pr-10', className)} {...props} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Hide password' : 'Show password'}
        className="text-muted-foreground hover:text-foreground focus-visible:ring-ring/30 absolute inset-y-0 right-0 flex items-center rounded-r-lg px-3 outline-none transition-colors focus-visible:ring-4"
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  )
}
