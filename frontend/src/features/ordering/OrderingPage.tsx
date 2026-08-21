import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft, ShoppingCart } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { useParams } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Sheet } from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { apiFetch } from '@/shared/api/client'
import type { OrderingFlowCustomerLookupOut, PublicMenuItemOut } from '@/shared/api/types'
import { ItemImage } from '@/shared/components/ItemImage'
import { formatOrderNumber } from '@/shared/lib/orderNumber'

import { useOrderingCheckout } from './useOrderingCheckout'
import { usePublicMenu } from './usePublicMenu'

// Meta's WhatsApp webhook always reports the sender as country code +
// local number with no "+", spaces, or leading zero (e.g. "919876543210")
// -- matching that exactly here is what lets the order confirmation find
// the same Customer row the inbound chat created, instead of typing
// mismatched formats into a free-text phone field creating a second one.
const COUNTRY_CODES = [
  { code: '91', label: 'India (+91)' },
  { code: '1', label: 'US/Canada (+1)' },
  { code: '44', label: 'UK (+44)' },
  { code: '971', label: 'UAE (+971)' },
  { code: '65', label: 'Singapore (+65)' },
  { code: '61', label: 'Australia (+61)' },
] as const

const checkoutSchema = z
  .object({
    country_code: z.string().min(1, 'Required'),
    local_number: z
      .string()
      .min(1, 'Required')
      .regex(/^\d{6,12}$/, 'Enter a valid mobile number (digits only)'),
    customer_display_name: z.string().trim().min(1, 'Please enter your name'),
    payment_method: z.enum(['online', 'cod']),
    order_type: z.enum(['pickup', 'delivery']),
    address_line1: z.string().optional(),
    address_line2: z.string().optional(),
    address_landmark: z.string().optional(),
    address_city: z.string().optional(),
    address_pincode: z.string().optional(),
    contact_choice: z.enum(['same', 'different']),
    contact_phone: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    if (values.order_type === 'delivery') {
      if (!values.address_line1?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['address_line1'],
          message: 'Required for delivery',
        })
      }
      if (!values.address_city?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['address_city'],
          message: 'Required for delivery',
        })
      }
      if (!values.address_pincode?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['address_pincode'],
          message: 'Required for delivery',
        })
      }
    }
    if (values.contact_choice === 'different') {
      const trimmed = values.contact_phone?.trim() ?? ''
      if (!/^\+?\d{7,15}$/.test(trimmed)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['contact_phone'],
          message: 'Enter a valid phone number',
        })
      }
    }
  })
type CheckoutForm = z.infer<typeof checkoutSchema>

type Cart = Record<string, number>

type MenuSection = { category: string; items: PublicMenuItemOut[] }

function groupByCategory(items: PublicMenuItemOut[]): MenuSection[] {
  const sections: MenuSection[] = []
  const indexByCategory = new Map<string, number>()
  for (const item of items) {
    const category = item.category.trim() || 'Other'
    const existingIndex = indexByCategory.get(category)
    if (existingIndex === undefined) {
      indexByCategory.set(category, sections.length)
      sections.push({ category, items: [item] })
    } else {
      sections[existingIndex]?.items.push(item)
    }
  }
  return sections
}

function cartStorageKey(merchantId: string): string {
  return `orderflow-cart:${merchantId}`
}

function loadStoredCart(merchantId: string): Cart {
  try {
    const raw = sessionStorage.getItem(cartStorageKey(merchantId))
    return raw ? (JSON.parse(raw) as Cart) : {}
  } catch {
    // Private browsing / storage disabled -- cart still works for the
    // current page load, it just won't survive a reload.
    return {}
  }
}

// The docked cart bar is `position: fixed`, which mobile browsers anchor
// to the *layout* viewport -- when the on-screen keyboard opens (typing a
// phone number or address), that layout viewport doesn't shrink, so the
// bar ends up pinned below the visible area, hidden behind the keyboard.
// This tracks how far the visual viewport has been pushed up and offsets
// the bar by the same amount so it stays on-screen.
function useKeyboardInset(): number {
  const [inset, setInset] = useState(0)

  useEffect(() => {
    const viewport = window.visualViewport
    if (!viewport) {
      return
    }
    const update = () => {
      const offset = window.innerHeight - viewport.height - viewport.offsetTop
      setInset(Math.max(0, Math.round(offset)))
    }
    update()
    viewport.addEventListener('resize', update)
    viewport.addEventListener('scroll', update)
    return () => {
      viewport.removeEventListener('resize', update)
      viewport.removeEventListener('scroll', update)
    }
  }, [])

  return inset
}

function categoryAnchor(category: string): string {
  const slug = category
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
  return `menu-category-${slug || 'other'}`
}

// Mirrors the menu's own category-header treatment (serif label + hairline
// rule) so the form reads as a continuation of the same considered layout
// instead of a plain stack of inputs bolted on underneath it.
function FormSectionHeading({ title }: { title: string }) {
  return (
    <div className="flex items-baseline gap-3 pt-1">
      <h3 className="font-serif text-base font-semibold">{title}</h3>
      <span className="bg-border h-px flex-1" />
    </div>
  )
}

function CartRow({
  item,
  quantity,
  onChange,
}: {
  item: PublicMenuItemOut
  quantity: number
  onChange: (quantity: number) => void
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-4 border-b px-4 py-4 transition-colors duration-150 last:border-0',
        quantity > 0 && 'bg-primary/5',
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <ItemImage url={item.image_url} name={item.name} />
        <div className="min-w-0">
          <p className="truncate font-medium">{item.name}</p>
          <p className="text-muted-foreground text-sm">INR {item.price}</p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => onChange(Math.max(0, quantity - 1))}
        >
          −
        </Button>
        <span className="w-5 text-center font-medium">{quantity}</span>
        <Button type="button" variant="outline" size="icon" onClick={() => onChange(quantity + 1)}>
          +
        </Button>
      </div>
    </div>
  )
}

export function OrderingPage() {
  const { merchantId } = useParams<{ merchantId: string }>()
  const { data: menu, isLoading, isError } = usePublicMenu(merchantId ?? '')
  const checkout = useOrderingCheckout(merchantId ?? '')
  const [cart, setCart] = useState<Cart>(() => (merchantId ? loadStoredCart(merchantId) : {}))
  const [isCartOpen, setIsCartOpen] = useState(false)
  const [isLookingUpCustomer, setIsLookingUpCustomer] = useState(false)
  const formSectionRef = useRef<HTMLDivElement>(null)
  const menuSectionRef = useRef<HTMLDivElement>(null)
  const keyboardInset = useKeyboardInset()

  // Persists across a reload -- backgrounding the WhatsApp in-app browser,
  // an accidental refresh, or navigating away and back with the device's
  // own back button were all silently wiping the cart before this, since
  // it previously lived only in memory.
  useEffect(() => {
    if (!merchantId) {
      return
    }
    try {
      sessionStorage.setItem(cartStorageKey(merchantId), JSON.stringify(cart))
    } catch {
      // Storage unavailable -- nothing to do, cart still works in-memory.
    }
  }, [cart, merchantId])

  // Once an order is actually placed, don't let it resurface on the next
  // visit to this merchant's page.
  useEffect(() => {
    if (!checkout.isSuccess || !merchantId) {
      return
    }
    try {
      sessionStorage.removeItem(cartStorageKey(merchantId))
    } catch {
      // Storage unavailable -- nothing to clean up.
    }
  }, [checkout.isSuccess, merchantId])

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    getValues,
    control,
    formState: { errors },
  } = useForm<CheckoutForm>({
    resolver: zodResolver(checkoutSchema),
    defaultValues: {
      payment_method: 'online',
      country_code: COUNTRY_CODES[0].code,
      order_type: 'pickup',
      contact_choice: 'same',
    },
  })

  const orderType = watch('order_type')
  const contactChoice = watch('contact_choice')
  const countryCode = watch('country_code')
  const localNumber = watch('local_number')
  const localNumberField = register('local_number')

  // Fires once the customer finishes entering their WhatsApp number --
  // returning customers get their saved name/address prefilled (still
  // editable) instead of typing it in again every order. A brand-new
  // number 404s, which is the normal case, not an error worth surfacing.
  const handlePhoneBlur = async () => {
    const countryCode = getValues('country_code')
    const localNumber = getValues('local_number')
    if (!merchantId || !/^\d{6,12}$/.test(localNumber)) {
      return
    }
    setIsLookingUpCustomer(true)
    try {
      const result = await apiFetch<OrderingFlowCustomerLookupOut>(
        `/api/v1/ordering-flow/${merchantId}/customer-lookup?whatsapp_number=${encodeURIComponent(
          `${countryCode}${localNumber}`,
        )}`,
      )
      if (result.display_name) {
        setValue('customer_display_name', result.display_name)
      }
      if (result.address) {
        setValue('address_line1', result.address.line1)
        setValue('address_line2', result.address.line2 ?? '')
        setValue('address_landmark', result.address.landmark ?? '')
        setValue('address_city', result.address.city)
        setValue('address_pincode', result.address.pincode)
      }
      if (result.default_contact_phone) {
        setValue('contact_choice', 'different')
        setValue('contact_phone', result.default_contact_phone)
      }
    } catch {
      // New customer, or a transient lookup failure -- this is a
      // convenience prefill, not a required step, so fail silently.
    } finally {
      setIsLookingUpCustomer(false)
    }
  }

  // The cart sheet and the "back to menu" link both need a way back up to
  // the menu -- without this, adding a second item once you've scrolled
  // into the checkout form means scrolling all the way back up by hand.
  const scrollToMenu = () => {
    setIsCartOpen(false)
    menuSectionRef.current?.scrollIntoView({ behavior: 'smooth' })
  }
  const scrollToCheckout = () => {
    setIsCartOpen(false)
    formSectionRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const menuSections = useMemo(() => groupByCategory(menu?.items ?? []), [menu])

  const cartLines = useMemo(
    () =>
      Object.entries(cart)
        .filter(([, quantity]) => quantity > 0)
        .map(([menuItemId, quantity]) => {
          const item = menu?.items.find((i) => i.menu_item_id === menuItemId)
          return item ? { item, quantity } : null
        })
        .filter((line): line is { item: PublicMenuItemOut; quantity: number } => line !== null),
    [cart, menu],
  )

  const cartItemCount = cartLines.reduce((sum, line) => sum + line.quantity, 0)
  const total = cartLines.reduce((sum, line) => sum + Number(line.item.price) * line.quantity, 0)

  if (isLoading) {
    // Shaped like the real layout below (title, category pills, item
    // rows) rather than a bare spinner, so the page doesn't visibly jump
    // once the menu arrives.
    return (
      <div className="from-background to-secondary/30 min-h-svh bg-gradient-to-b">
        <div className="mx-auto max-w-md space-y-6 px-4 py-8">
          <div className="motion-safe:animate-pulse space-y-2 text-center">
            <div className="bg-muted mx-auto h-3 w-20 rounded" />
            <div className="bg-muted mx-auto h-7 w-48 rounded" />
          </div>
          <div className="motion-safe:animate-pulse flex gap-2">
            {['w-16', 'w-20', 'w-14', 'w-24'].map((width) => (
              <div key={width} className={cn('bg-muted h-7 rounded-full', width)} />
            ))}
          </div>
          <Card className="divide-border motion-safe:animate-pulse overflow-hidden py-0">
            {[0, 1, 2].map((row) => (
              <div key={row} className="flex items-center gap-3 border-b px-4 py-4 last:border-0">
                <div className="bg-muted size-11 shrink-0 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <div className="bg-muted h-4 w-2/3 rounded" />
                  <div className="bg-muted h-3 w-1/4 rounded" />
                </div>
              </div>
            ))}
          </Card>
        </div>
      </div>
    )
  }

  if (isError || !menu) {
    return (
      <div className="flex min-h-svh items-center justify-center p-8">
        <p className="text-muted-foreground text-sm">Restaurant not found.</p>
      </div>
    )
  }

  const onSubmit = (values: CheckoutForm) => {
    checkout.mutate({
      customer_whatsapp_number: `${values.country_code}${values.local_number}`,
      customer_display_name: values.customer_display_name,
      payment_method: values.payment_method,
      order_type: values.order_type,
      items: cartLines.map((line) => ({
        menu_item_id: line.item.menu_item_id,
        quantity: line.quantity,
      })),
      contact_phone:
        values.contact_choice === 'different' ? (values.contact_phone ?? '').trim() : undefined,
      ...(values.order_type === 'delivery'
        ? {
            delivery_address: {
              line1: (values.address_line1 ?? '').trim(),
              line2: values.address_line2?.trim() || undefined,
              landmark: values.address_landmark?.trim() || undefined,
              city: (values.address_city ?? '').trim(),
              pincode: (values.address_pincode ?? '').trim(),
            },
          }
        : {}),
    })
  }

  if (checkout.isSuccess) {
    // A website can't programmatically hand control back to the WhatsApp
    // app -- that's a platform restriction on both iOS and Android, not
    // something fixable here -- so this is a one-tap link, not an
    // automatic return.
    const whatsappNumber = menu.merchant_whatsapp_number?.replace(/\D/g, '')

    const orderTypeLabel = getValues('order_type') === 'delivery' ? 'Delivery' : 'Pickup'
    const paymentOutstanding = Boolean(checkout.data.payment_link_url)

    return (
      <div className="from-background to-secondary/40 flex min-h-svh items-center justify-center bg-gradient-to-b p-6">
        <Card className="w-full max-w-sm space-y-5 p-8 text-center shadow-lg">
          <span className="bg-primary text-primary-foreground mx-auto flex size-12 items-center justify-center rounded-full text-xl">
            ✓
          </span>
          <div className="space-y-1">
            <h1 className="font-serif text-xl font-semibold">
              Order {formatOrderNumber(checkout.data.order_number)} confirmed!
            </h1>
            <p className="text-muted-foreground text-sm">
              {paymentOutstanding
                ? 'Complete payment and we’ll get started.'
                : 'We’ll let you know when it’s ready.'}
            </p>
          </div>

          <div className="bg-secondary/40 space-y-1.5 rounded-lg border p-4 text-left text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">{orderTypeLabel}</span>
              <span className="font-medium">
                {cartItemCount} item{cartItemCount === 1 ? '' : 's'}
              </span>
            </div>
            <div className="flex items-center justify-between border-t pt-1.5">
              <span className="font-medium">Total</span>
              <span className="text-brand-gold font-serif font-semibold">
                INR {total.toFixed(2)}
              </span>
            </div>
          </div>

          {checkout.data.payment_link_url && (
            <Button asChild size="lg" className="w-full">
              {/* Same-tab navigation, not target="_blank" -- inside WhatsApp's
                  in-app browser, opening a new tab stacks an extra browser
                  layer on top of an already-embedded view. Razorpay UPI
                  Payment Links (Live Mode merchants) go straight to a UPI
                  app picker from here instead of a full checkout page. */}
              <a href={checkout.data.payment_link_url}>Complete payment</a>
            </Button>
          )}
          {whatsappNumber && (
            <a
              href={`https://wa.me/${whatsappNumber}`}
              className="text-muted-foreground hover:text-foreground block text-sm underline-offset-4 transition-colors duration-150 hover:underline"
            >
              Return to WhatsApp chat
            </a>
          )}
        </Card>
      </div>
    )
  }

  return (
    <div className="from-background to-secondary/30 min-h-svh bg-gradient-to-b">
      <div className={cn('mx-auto max-w-md space-y-6 px-4 py-8', cartLines.length > 0 && 'pb-28')}>
        <div className="space-y-1 text-center">
          <p className="text-muted-foreground text-xs tracking-wide uppercase">Order from</p>
          <h1 className="font-serif text-2xl font-semibold">{menu.business_name}</h1>
        </div>

        {menuSections.length > 1 && (
          <nav className="bg-background/95 supports-[backdrop-filter]:backdrop-blur sticky top-0 z-10 -mx-4 flex gap-2 overflow-x-auto border-b px-4 py-2.5 sm:mx-0 sm:rounded-xl sm:border">
            {menuSections.map((section) => (
              <a
                key={section.category}
                href={`#${categoryAnchor(section.category)}`}
                className="border-border bg-card text-muted-foreground hover:border-brand-gold/50 hover:text-foreground shrink-0 rounded-full border px-3 py-1 text-xs font-medium whitespace-nowrap transition-colors duration-150"
              >
                {section.category}
              </a>
            ))}
          </nav>
        )}

        {menuSections.length === 0 && (
          <Card className="p-6 text-center">
            <p className="text-muted-foreground text-sm">No items available right now.</p>
          </Card>
        )}

        <div ref={menuSectionRef} className="space-y-8 scroll-mt-16">
          {menuSections.map((section) => (
            <section
              key={section.category}
              id={categoryAnchor(section.category)}
              className="scroll-mt-16"
            >
              <div className="mb-3 flex items-baseline gap-3">
                <h2 className="font-serif text-lg font-semibold">{section.category}</h2>
                <span className="bg-border h-px flex-1" />
                <span className="text-muted-foreground text-xs">
                  {section.items.length} item{section.items.length === 1 ? '' : 's'}
                </span>
              </div>
              <Card className="divide-border overflow-hidden py-0">
                {section.items.map((item) => (
                  <CartRow
                    key={item.menu_item_id}
                    item={item}
                    quantity={cart[item.menu_item_id] ?? 0}
                    onChange={(quantity) =>
                      setCart((prev) => ({ ...prev, [item.menu_item_id]: quantity }))
                    }
                  />
                ))}
              </Card>
            </section>
          ))}
        </div>

        {cartLines.length > 0 && (
          <div ref={formSectionRef} className="scroll-mt-16">
            <form onSubmit={handleSubmit(onSubmit)}>
              <Card className="space-y-4 p-5">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-lg font-medium">
                    Total:{' '}
                    <span className="font-serif text-brand-gold font-semibold">
                      INR {total.toFixed(2)}
                    </span>
                  </p>
                  <button
                    type="button"
                    onClick={scrollToMenu}
                    className="text-primary inline-flex shrink-0 items-center gap-1 text-sm font-medium transition-colors duration-150 hover:underline"
                  >
                    <ArrowLeft className="size-3.5" />
                    Back to menu
                  </button>
                </div>

                {/* Fulfillment first: it decides whether the address block
                    below even applies, so it can't come after it. */}
                <FormSectionHeading title="How would you like this?" />
                <div className="space-y-2">
                  <Label className="sr-only">Order type</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setValue('order_type', 'pickup', { shouldValidate: true })}
                      className={cn(
                        'rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors duration-150',
                        orderType === 'pickup'
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-input bg-card text-muted-foreground hover:border-ring/30',
                      )}
                    >
                      Pickup
                    </button>
                    <button
                      type="button"
                      onClick={() => setValue('order_type', 'delivery', { shouldValidate: true })}
                      className={cn(
                        'rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors duration-150',
                        orderType === 'delivery'
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-input bg-card text-muted-foreground hover:border-ring/30',
                      )}
                    >
                      Delivery
                    </button>
                  </div>
                </div>

                <FormSectionHeading title="Your details" />
                <div className="space-y-2">
                  <Label htmlFor="local_number">Your WhatsApp number</Label>
                  <div className="flex gap-2">
                    <Controller
                      name="country_code"
                      control={control}
                      render={({ field }) => (
                        <Select value={field.value} onValueChange={field.onChange}>
                          <SelectTrigger
                            id="country_code"
                            aria-label="Country code"
                            onBlur={field.onBlur}
                            className="w-36 shrink-0"
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {COUNTRY_CODES.map(({ code, label }) => (
                              <SelectItem key={code} value={code}>
                                {label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                    <Input
                      id="local_number"
                      inputMode="numeric"
                      placeholder="9876543210"
                      {...localNumberField}
                      onBlur={(event) => {
                        void localNumberField.onBlur(event)
                        void handlePhoneBlur()
                      }}
                    />
                  </div>
                  {errors.local_number && (
                    <p className="text-destructive text-sm">{errors.local_number.message}</p>
                  )}
                  {isLookingUpCustomer && (
                    <p className="text-muted-foreground text-xs">Checking for saved details…</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="customer_display_name">Your name</Label>
                  <Input id="customer_display_name" {...register('customer_display_name')} />
                  {errors.customer_display_name && (
                    <p className="text-destructive text-sm">
                      {errors.customer_display_name.message}
                    </p>
                  )}
                </div>

                {orderType === 'delivery' && (
                  <div className="border-border space-y-3 rounded-lg border border-dashed p-3">
                    <div className="space-y-2">
                      <Label htmlFor="address_line1">Address line 1</Label>
                      <Input
                        id="address_line1"
                        placeholder="House / flat no., building, street"
                        {...register('address_line1')}
                      />
                      {errors.address_line1 && (
                        <p className="text-destructive text-sm">{errors.address_line1.message}</p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="address_line2">Address line 2 (optional)</Label>
                      <Input id="address_line2" {...register('address_line2')} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="address_landmark">Landmark (optional)</Label>
                      <Input id="address_landmark" {...register('address_landmark')} />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2">
                        <Label htmlFor="address_city">City</Label>
                        <Input id="address_city" {...register('address_city')} />
                        {errors.address_city && (
                          <p className="text-destructive text-sm">{errors.address_city.message}</p>
                        )}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="address_pincode">Pincode</Label>
                        <Input
                          id="address_pincode"
                          inputMode="numeric"
                          {...register('address_pincode')}
                        />
                        {errors.address_pincode && (
                          <p className="text-destructive text-sm">
                            {errors.address_pincode.message}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                <FormSectionHeading title="Payment" />
                <div className="space-y-2">
                  <Label>Contact number for this order</Label>
                  <div className="space-y-2">
                    <button
                      type="button"
                      onClick={() => setValue('contact_choice', 'same', { shouldValidate: true })}
                      className={cn(
                        'w-full rounded-lg border px-4 py-2.5 text-left text-sm transition-colors duration-150',
                        contactChoice === 'same'
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-input bg-card text-muted-foreground hover:border-ring/30',
                      )}
                    >
                      <span className="block font-medium">Use my WhatsApp number</span>
                      <span className="block text-xs opacity-80">
                        {countryCode && localNumber
                          ? `+${countryCode} ${localNumber} as entered above`
                          : 'As entered above'}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setValue('contact_choice', 'different', { shouldValidate: true })
                      }
                      className={cn(
                        'w-full rounded-lg border px-4 py-2.5 text-left text-sm transition-colors duration-150',
                        contactChoice === 'different'
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-input bg-card text-muted-foreground hover:border-ring/30',
                      )}
                    >
                      <span className="block font-medium">Use a different number</span>
                      <span className="block text-xs opacity-80">
                        e.g. reception or a family member who can take the delivery call
                      </span>
                    </button>
                  </div>
                  {contactChoice === 'different' && (
                    <div className="space-y-2 pt-1">
                      <Label htmlFor="contact_phone">Number to call</Label>
                      <Input
                        id="contact_phone"
                        inputMode="tel"
                        placeholder="e.g. 9876543210"
                        {...register('contact_phone')}
                      />
                      {errors.contact_phone && (
                        <p className="text-destructive text-sm">{errors.contact_phone.message}</p>
                      )}
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="payment_method">Payment method</Label>
                  <Controller
                    name="payment_method"
                    control={control}
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger id="payment_method" onBlur={field.onBlur} className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="online">Pay online</SelectItem>
                          <SelectItem value="cod">Cash on delivery/pickup</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>

                {checkout.isError && (
                  <p className="text-destructive text-sm">
                    Something went wrong placing your order. Please try again.
                  </p>
                )}

                <Button type="submit" size="lg" className="w-full" disabled={checkout.isPending}>
                  {checkout.isPending ? 'Placing order…' : 'Place order'}
                </Button>
              </Card>
            </form>
          </div>
        )}
      </div>

      {cartLines.length > 0 && (
        <div
          // Standard Tailwind `shadow-*` utilities cast a downward/
          // all-around shadow, which is invisible on a bar pinned to the
          // bottom edge of the viewport -- there's no utility for an
          // upward-cast shadow, so this stays a custom arbitrary value.
          // Tuned per-theme rather than reusing one rgba value everywhere:
          // the light-mode figure reads as a soft lift off the page, but
          // the same black-based shadow all but disappears against the
          // app's near-black dark background, so the dark variant raises
          // opacity/blur to stay visible there too.
          className="fixed inset-x-0 z-20 border-t bg-card/95 p-3 shadow-[0_-4px_16px_rgba(0,0,0,0.08)] backdrop-blur dark:shadow-[0_-4px_20px_rgba(0,0,0,0.45)]"
          style={{ bottom: keyboardInset }}
        >
          {/* Always present once there's something in the cart -- through
              the menu, the form, and everything in between -- and always
              opens the cart rather than only ever pushing further into
              checkout, so there's a way back no matter how far down the
              page you've scrolled. `bottom` tracks the on-screen keyboard
              (see useKeyboardInset) so typing a phone number or address
              doesn't push this off-screen. */}
          <button
            type="button"
            onClick={() => setIsCartOpen(true)}
            className="bg-primary text-primary-foreground mx-auto flex w-full max-w-md items-center justify-between rounded-lg px-4 py-3 text-sm font-medium shadow-sm transition-all duration-150 active:scale-[0.98]"
          >
            <span className="flex items-center gap-2">
              <ShoppingCart className="size-4" />
              <span
                key={cartItemCount}
                className="motion-safe:animate-in motion-safe:zoom-in-50 motion-safe:duration-300 inline-block"
              >
                {cartItemCount} item{cartItemCount === 1 ? '' : 's'}
              </span>
              in cart
            </span>
            <span>
              <span className="text-brand-gold font-serif">INR {total.toFixed(2)}</span> · View cart
            </span>
          </button>
        </div>
      )}

      <Sheet
        open={isCartOpen}
        onOpenChange={setIsCartOpen}
        title="Your cart"
        footer={
          <>
            <Button type="button" variant="outline" className="w-full" onClick={scrollToMenu}>
              + Add more items
            </Button>
            <Button type="button" className="w-full" onClick={scrollToCheckout}>
              Continue to checkout
            </Button>
          </>
        }
      >
        {cartLines.length === 0 ? (
          <p className="text-muted-foreground text-sm">Your cart is empty.</p>
        ) : (
          <div className="-mx-1">
            {cartLines.map(({ item, quantity }) => (
              <CartRow
                key={item.menu_item_id}
                item={item}
                quantity={quantity}
                onChange={(nextQuantity) =>
                  setCart((prev) => ({ ...prev, [item.menu_item_id]: nextQuantity }))
                }
              />
            ))}
          </div>
        )}
      </Sheet>
    </div>
  )
}
