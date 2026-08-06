import { zodResolver } from '@hookform/resolvers/zod'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useParams } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
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
    <div className="flex items-center justify-between gap-4 border-b py-3 last:border-0">
      <div>
        <p className="font-medium">{item.name}</p>
        <p className="text-muted-foreground text-sm">
          {item.category} · INR {item.price}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => onChange(Math.max(0, quantity - 1))}
        >
          −
        </Button>
        <span className="w-6 text-center">{quantity}</span>
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
    return <p className="p-8 text-center text-muted-foreground">Loading menu…</p>
  }

  if (isError || !menu) {
    return <p className="p-8 text-center text-muted-foreground">Restaurant not found.</p>
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
      <div className="mx-auto max-w-md space-y-4 p-8 text-center">
        <h1 className="text-xl font-semibold">Order confirmed!</h1>
        <p className="text-muted-foreground text-sm">We'll let you know when it's ready.</p>
        {checkout.data.payment_link_url && (
          <Button asChild>
            <a href={checkout.data.payment_link_url} target="_blank" rel="noreferrer">
              Complete payment
            </a>
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md space-y-6 p-6">
      <h1 className="text-2xl font-semibold">{menu.business_name}</h1>

      <div className="rounded-md border p-2">
        {menu.items.length === 0 && (
          <p className="text-muted-foreground p-4 text-center text-sm">
            No items available right now.
          </p>
        )}
        {menu.items.map((item) => (
          <CartRow
            key={item.menu_item_id}
            item={item}
            quantity={cart[item.menu_item_id] ?? 0}
            onChange={(quantity) => setCart((prev) => ({ ...prev, [item.menu_item_id]: quantity }))}
          />
        ))}
      </div>

      {cartLines.length > 0 && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 rounded-md border p-4">
          <p className="text-lg font-medium">Total: INR {total.toFixed(2)}</p>

          <div className="space-y-2">
            <Label htmlFor="customer_whatsapp_number">Your phone number</Label>
            <Input
              id="customer_whatsapp_number"
              placeholder="+919876543210"
              {...register('customer_whatsapp_number')}
            />
            {errors.customer_whatsapp_number && (
              <p className="text-destructive text-sm">{errors.customer_whatsapp_number.message}</p>
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
              className="border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm"
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

          <Button type="submit" className="w-full" disabled={checkout.isPending}>
            {checkout.isPending ? 'Placing order…' : 'Place order'}
          </Button>
        </form>
      )}
    </div>
  )
}
