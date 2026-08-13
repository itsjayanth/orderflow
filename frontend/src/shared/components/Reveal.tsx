import { createElement, type ElementType, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { useInView } from '@/shared/hooks/useInView'

/**
 * Fades + lifts children into place the first time they scroll into view.
 * Purely a presentation nicety -- content is always in the DOM and readable
 * without JS/animation; `prefers-reduced-motion` skips the transition
 * entirely (see `useInView`) rather than just shortening it.
 */
export function Reveal({
  children,
  className,
  as = 'div',
  delayMs = 0,
}: {
  children: ReactNode
  className?: string
  as?: ElementType
  delayMs?: number
}) {
  const { ref, inView } = useInView<HTMLElement>()

  return createElement(
    as,
    {
      ref,
      className: cn(
        'transition-[opacity,transform] duration-700 ease-out',
        inView ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0',
        className,
      ),
      style: delayMs ? { transitionDelay: `${delayMs}ms` } : undefined,
    },
    children,
  )
}
