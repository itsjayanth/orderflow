import type { LucideIcon } from 'lucide-react'
import { Check, Monitor, Moon, Sun } from 'lucide-react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

import { useTheme } from './ThemeProvider'

const THEME_OPTIONS: { value: 'light' | 'dark' | 'system'; label: string; icon: LucideIcon }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

// Trigger icon reflects the *resolved* theme (what's actually on screen
// right now), not the stored mode -- so a mode of "system" still shows a
// sensible Sun/Moon rather than a generic third icon. Not mounted anywhere
// yet (that's Phase 2's nav shell); this is the ready-to-use control.
export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme()
  const TriggerIcon = resolvedTheme === 'dark' ? Moon : Sun

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Toggle theme"
          className="hover:bg-accent hover:text-accent-foreground focus-visible:ring-ring/30 inline-flex size-9 items-center justify-center rounded-lg outline-none transition-colors duration-150 focus-visible:ring-4"
        >
          <TriggerIcon className="size-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-36">
        {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
          <DropdownMenuItem key={value} onSelect={() => setTheme(value)}>
            <Icon />
            {label}
            {theme === value && <Check className="ml-auto size-4" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
