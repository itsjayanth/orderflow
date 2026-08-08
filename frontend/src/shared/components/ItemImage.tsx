import { useState } from 'react'

import { cn } from '@/lib/utils'

interface ItemImageProps {
  url: string | null
  name: string
  className?: string
}

// There's no file-upload/CDN infrastructure in this app -- menu item photos
// are a merchant-pasted URL to an already-hosted image, so a broken/missing
// URL is an expected, common case rather than an error. Falls back to a
// plain initial-letter tile (no placeholder asset needed) both when
// image_url is unset and when the URL fails to load.
export function ItemImage({ url, name, className }: ItemImageProps) {
  const [broken, setBroken] = useState(false)

  if (url && !broken) {
    return (
      <img
        src={url}
        alt={name}
        className={cn('border-border size-12 shrink-0 rounded-lg border object-cover', className)}
        onError={() => setBroken(true)}
      />
    )
  }

  return (
    <div
      aria-hidden="true"
      className={cn(
        'border-border bg-secondary text-secondary-foreground flex size-12 shrink-0 items-center justify-center rounded-lg border font-serif text-lg font-semibold',
        className,
      )}
    >
      {name.trim().charAt(0).toUpperCase() || '?'}
    </div>
  )
}
