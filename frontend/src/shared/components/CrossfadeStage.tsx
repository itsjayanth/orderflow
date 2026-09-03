import { type ReactNode, useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion'

/**
 * Swaps `children` whenever `stageKey` changes with a fade+slide transition
 * instead of a hard remount -- used for the List/Calendar stage and the
 * Week/Day/Month sub-stage on the Appointments page. Deliberately a
 * sequential swap (new content fades in over the old content's slot) rather
 * than a dual-mounted overlap crossfade: the stages here have very
 * different heights (a table vs. a fixed-height calendar), and overlapping
 * two absolutely-positioned stages of different height causes layout
 * collapse/jank. `prefers-reduced-motion: reduce` swaps instantly, matching
 * the one-shot check in shared/hooks/useInView.ts.
 */
export function CrossfadeStage({
  stageKey,
  children,
  className,
}: {
  stageKey: string
  children: ReactNode
  className?: string
}) {
  const reducedMotion = usePrefersReducedMotion()
  const [displayedKey, setDisplayedKey] = useState(stageKey)
  const [displayedChildren, setDisplayedChildren] = useState(children)
  const [entering, setEntering] = useState(false)
  const frameRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (stageKey === displayedKey) {
      setDisplayedChildren(children)
      return
    }
    if (reducedMotion) {
      setDisplayedKey(stageKey)
      setDisplayedChildren(children)
      return
    }
    setDisplayedKey(stageKey)
    setDisplayedChildren(children)
    setEntering(true)
    cancelAnimationFrame(frameRef.current ?? 0)
    // Two rAFs so the "entering" (faded-out) styles paint for a frame
    // before transitioning to visible -- one rAF can land in the same
    // paint as the state change in some browsers, skipping the animation.
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = requestAnimationFrame(() => setEntering(false))
    })
    return () => cancelAnimationFrame(frameRef.current ?? 0)
  }, [stageKey, children, displayedKey, reducedMotion])

  useEffect(() => () => cancelAnimationFrame(frameRef.current ?? 0), [])

  return (
    <div
      className={cn(
        'transition-[opacity,transform] ease-out',
        reducedMotion ? 'duration-0' : 'duration-[220ms]',
        entering ? 'translate-y-1 opacity-0' : 'translate-y-0 opacity-100',
        className,
      )}
    >
      {displayedChildren}
    </div>
  )
}
