import type * as React from 'react'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

type Theme = 'light' | 'dark' | 'system'
type ResolvedTheme = 'light' | 'dark'

interface ThemeContextValue {
  theme: Theme
  setTheme: (theme: Theme) => void
  resolvedTheme: ResolvedTheme
}

const STORAGE_KEY = 'orderflow-theme'

const ThemeContext = createContext<ThemeContextValue | null>(null)

function isTheme(value: string | null): value is Theme {
  return value === 'light' || value === 'dark' || value === 'system'
}

function getSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function readStoredTheme(): Theme {
  if (typeof window === 'undefined') return 'system'
  // localStorage access can throw (Safari private browsing, some sandboxed
  // test/embed environments) -- fall back to 'system' rather than crashing.
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return isTheme(stored) ? stored : 'system'
  } catch {
    return 'system'
  }
}

function applyResolvedTheme(resolved: ResolvedTheme) {
  document.documentElement.classList.toggle('dark', resolved === 'dark')
}

// React context + localStorage-persisted theme mode, mirrored onto the
// `.dark` class on <html> -- index.css's `@custom-variant dark (&:is(.dark
// *))` is what actually activates the dark token set, this provider is
// just what decides when that class is present. Defaults to 'system' on
// first load (no stored preference yet) and tracks the OS-level media
// query live while mode is 'system', so a user who never touches the
// toggle still gets a correct/live dark mode.
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => readStoredTheme())
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
    theme === 'system' ? getSystemTheme() : theme,
  )

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.setItem(STORAGE_KEY, next)
      } catch {
        // See readStoredTheme -- persistence is best-effort.
      }
    }
  }, [])

  useEffect(() => {
    if (theme !== 'system') {
      setResolvedTheme(theme)
      applyResolvedTheme(theme)
      return
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const updateFromSystem = () => {
      const next = mediaQuery.matches ? 'dark' : 'light'
      setResolvedTheme(next)
      applyResolvedTheme(next)
    }

    updateFromSystem()
    mediaQuery.addEventListener('change', updateFromSystem)
    return () => mediaQuery.removeEventListener('change', updateFromSystem)
  }, [theme])

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, setTheme, resolvedTheme }),
    [theme, setTheme, resolvedTheme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
