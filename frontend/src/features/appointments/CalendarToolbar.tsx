import { format } from 'date-fns'
import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import type { ToolbarProps, View } from 'react-big-calendar'
import { Views } from 'react-big-calendar'

import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion'

const VIEW_OPTIONS: { value: View; label: string }[] = [
  { value: Views.WEEK, label: 'Week' },
  { value: Views.DAY, label: 'Day' },
  { value: Views.MONTH, label: 'Month' },
]

const MONTH_NAMES = Array.from({ length: 12 }, (_, i) => format(new Date(2000, i, 1), 'LLLL'))

// "current year" here means the year this module was loaded, not the date
// currently displayed on the calendar -- a tab left open across a year
// boundary would need a refresh to see the range shift, which is an
// acceptable tradeoff for a quick-jump control.
const CURRENT_YEAR = new Date().getFullYear()
const YEAR_OPTIONS = Array.from({ length: 11 }, (_, i) => CURRENT_YEAR - 5 + i)

function availableViewOptions(views: ToolbarProps['views']): typeof VIEW_OPTIONS {
  if (Array.isArray(views)) {
    return VIEW_OPTIONS.filter((option) => views.includes(option.value))
  }
  return VIEW_OPTIONS
}

/**
 * Custom react-big-calendar toolbar restyled with this app's shadcn
 * components. Keeps the same Back/Next/Today navigation and Week/Day/Month
 * switching the default toolbar provides, adds a sliding underline
 * indicator under the active view tab, and a month/year quick-jump popover.
 */
export function CalendarToolbar({ date, label, view, views, onNavigate, onView }: ToolbarProps) {
  const reducedMotion = usePrefersReducedMotion()
  const viewOptions = availableViewOptions(views)

  const tabsWrapperRef = useRef<HTMLDivElement>(null)
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null)

  const measureIndicator = useCallback(() => {
    const wrapper = tabsWrapperRef.current
    if (!wrapper) return
    const active = wrapper.querySelector<HTMLElement>(
      '[data-slot="tabs-trigger"][data-state="active"]',
    )
    if (!active) return
    const wrapperRect = wrapper.getBoundingClientRect()
    const activeRect = active.getBoundingClientRect()
    setIndicator({ left: activeRect.left - wrapperRect.left, width: activeRect.width })
  }, [])

  useLayoutEffect(() => {
    measureIndicator()
  }, [measureIndicator, view])

  useLayoutEffect(() => {
    window.addEventListener('resize', measureIndicator)
    return () => window.removeEventListener('resize', measureIndicator)
  }, [measureIndicator])

  const [jumpOpen, setJumpOpen] = useState(false)
  const [jumpMonth, setJumpMonth] = useState(date.getMonth())
  const [jumpYear, setJumpYear] = useState(date.getFullYear())

  function handleJumpOpenChange(open: boolean) {
    setJumpOpen(open)
    if (open) {
      // Re-sync the selects to whatever the calendar is currently showing
      // each time the popover opens, rather than remembering the last pick.
      setJumpMonth(date.getMonth())
      setJumpYear(date.getFullYear())
    }
  }

  function handleJumpGo() {
    onNavigate('DATE', new Date(jumpYear, jumpMonth, 1))
    setJumpOpen(false)
  }

  return (
    <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-1.5">
        <Button variant="outline" size="sm" onClick={() => onNavigate('TODAY')}>
          Today
        </Button>
        <Button variant="outline" size="sm" onClick={() => onNavigate('PREV')}>
          Back
        </Button>
        <Button variant="outline" size="sm" onClick={() => onNavigate('NEXT')}>
          Next
        </Button>

        <Popover open={jumpOpen} onOpenChange={handleJumpOpenChange}>
          <PopoverTrigger asChild>
            <Button variant="outline" size="sm" className="ml-1 min-w-28 font-semibold">
              {label}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-64 space-y-3" align="start">
            <div className="grid grid-cols-2 gap-2">
              <Select value={String(jumpMonth)} onValueChange={(v) => setJumpMonth(Number(v))}>
                <SelectTrigger aria-label="Jump to month">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MONTH_NAMES.map((name, index) => (
                    <SelectItem key={name} value={String(index)}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={String(jumpYear)} onValueChange={(v) => setJumpYear(Number(v))}>
                <SelectTrigger aria-label="Jump to year">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {YEAR_OPTIONS.map((year) => (
                    <SelectItem key={year} value={String(year)}>
                      {year}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button size="sm" className="w-full" onClick={handleJumpGo}>
              Go
            </Button>
          </PopoverContent>
        </Popover>
      </div>

      <div ref={tabsWrapperRef} className="relative">
        <Tabs value={view} onValueChange={(value) => onView(value as View)}>
          <TabsList className="border-b-0">
            {viewOptions.map((option) => (
              <TabsTrigger key={option.value} value={option.value} className="after:hidden">
                {option.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <span
          aria-hidden="true"
          className={[
            'bg-primary pointer-events-none absolute bottom-0 h-0.5 rounded-full',
            reducedMotion ? '' : 'transition-[transform,width] duration-[220ms] ease-out',
          ].join(' ')}
          style={{
            width: indicator ? `${indicator.width}px` : 0,
            transform: `translateX(${indicator?.left ?? 0}px)`,
          }}
        />
      </div>
    </div>
  )
}
