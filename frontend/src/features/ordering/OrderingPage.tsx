import { zodResolver } from '@hookform/resolvers/zod'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useParams } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { PublicMenuItemOut } from '@/shared/api/types'

import { useOrderingCheckout } from './useOrderingCheckout'
import { usePublicMenu } from './usePublicMenu'

const checkoutSchema = z.object({
  customer_whatsapp_number: z.string().min(1, 'Required'),
  customer_display_name: z.string().optional(),
  payment_method: z.enum(['online', 'cod']),
})
type CheckoutForm = z.infer<typeof checkoutSchema>

type Cart = Record<string, number>

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
    <div className="flex items-center justify-between gap-4 border-b px-4 py-4 last:border-0">
      <div>
        <p className="font-medium">{item.name}</p>
        <p className="text-muted-foreground text-sm">
          {item.category} · INR {item.price}
        </p>
      </div>
      <div className="flex items-center gap-3">
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
  const [cart, setCart] = useState<Cart>({})

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CheckoutForm>({
    resolver: zodResolver(checkoutSchema),
    defaultValues: { payment_method: 'online' },
  })

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

  const total = cartLines.reduce((sum, line) => sum + Number(line.item.price) * line.quantity, 0)

  if (isLoading) {
    return (
      <div className="flex min-h-svh items-center justify-center p-8">
        <p className="text-muted-foreground text-sm">Loading menu…</p>
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
      customer_whatsapp_number: values.customer_whatsapp_number,
      customer_display_name: values.customer_display_name || undefined,
      payment_method: values.payment_method,
      items: cartLines.map((line) => ({
        menu_item_id: line.item.menu_item_id,
        quantity: line.quantity,
      })),
    })
  }

  if (checkout.isSuccess) {
    return (
      <div className="from-background to-secondary/40 flex min-h-svh items-center justify-center bg-gradient-to-b p-6">
        <Card className="w-full max-w-sm space-y-4 p-8 text-center shadow-lg">
          <span className="bg-primary text-primary-foreground mx-auto flex size-12 items-center justify-center rounded-full text-xl">
            ✓
          </span>
          <h1 className="font-serif text-xl font-semibold">Order confirmed!</h1>
          <p className="text-muted-foreground text-sm">We'll let you know when it's ready.</p>
          {checkout.data.payment_link_url && (
            <Button asChild className="w-full">
              <a href={checkout.data.payment_link_url} target="_blank" rel="noreferrer">
                Complete payment
              </a>
            </Button>
          )}
        </Card>
      </div>
    )
  }

  return (
    <div className="from-background to-secondary/30 min-h-svh bg-gradient-to-b">
      <div className="mx-auto max-w-md space-y-6 px-4 py-8">
        <div className="space-y-1 text-center">
          <p className="text-muted-foreground text-xs tracking-wide uppercase">Order from</p>
          <h1 className="font-serif text-2xl font-semibold">{menu.business_name}</h1>
        </div>

        <Card className="overflow-hidden py-0">
          {menu.items.length === 0 && (
            <p className="text-muted-foreground p-6 text-center text-sm">
              No items available right now.
            </p>
          )}
          {menu.items.map((item) => (
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

        {cartLines.length > 0 && (
          <form onSubmit={handleSubmit(onSubmit)}>
            <Card className="space-y-4 p-5">
              <p className="text-lg font-medium">Total: INR {total.toFixed(2)}</p>

              <div className="space-y-2">
                <Label htmlFor="customer_whatsapp_number">Your phone number</Label>
                <Input
                  id="customer_whatsapp_number"
                  placeholder="+919876543210"
                  {...register('customer_whatsapp_number')}
                />
                {errors.customer_whatsapp_number && (
                  <p className="text-destructive text-sm">
                    {errors.customer_whatsapp_number.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="customer_display_name">Your name (optional)</Label>
                <Input id="customer_display_name" {...register('customer_display_name')} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="payment_method">Payment method</Label>
                <select
                  id="payment_method"
                  className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/30 h-10 w-full rounded-lg border px-3.5 text-sm shadow-xs transition-all duration-150 outline-none focus-visible:ring-4"
                  {...register('payment_method')}
                >
                  <option value="online">Pay online</option>
                  <option value="cod">Cash on delivery/pickup</option>
                </select>
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
        )}
      </div>
    </div>
  )
}
