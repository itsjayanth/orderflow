import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useMenuItems } from '@/features/catalog/useMenuItems'

import { useTestCheckout } from './useTestCheckout'

const schema = z.object({
  customer_whatsapp_number: z.string().min(1, 'Required'),
  customer_display_name: z.string().optional(),
  menu_item_id: z.string().min(1, 'Pick an item'),
  quantity: z.number().int().min(1),
  payment_method: z.enum(['online', 'cod']),
})
type FormValues = z.infer<typeof schema>

export function CreateTestOrderForm() {
  const [open, setOpen] = useState(false)
  const { data: menuItems } = useMenuItems()
  const checkout = useTestCheckout()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { quantity: 1, payment_method: 'online' },
  })

  if (!open) {
    return (
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        + New test order
      </Button>
    )
  }

  const onSubmit = (values: FormValues) => {
    checkout.mutate(
      {
        customer_whatsapp_number: values.customer_whatsapp_number,
        customer_display_name: values.customer_display_name || undefined,
        items: [{ menu_item_id: values.menu_item_id, quantity: values.quantity }],
        payment_method: values.payment_method,
      },
      { onSuccess: () => reset({ quantity: 1, payment_method: 'online' }) },
    )
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="max-w-md space-y-4 rounded-md border p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">New test order</h2>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-muted-foreground text-sm hover:underline"
        >
          Close
        </button>
      </div>
      <p className="text-muted-foreground text-sm">
        Stands in for the WhatsApp ordering flow until Phase 6 exists -- finds or creates the
        customer by phone number.
      </p>

      <div className="space-y-2">
        <Label htmlFor="customer_whatsapp_number">Customer phone number</Label>
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
        <Label htmlFor="customer_display_name">Customer name (optional)</Label>
        <Input id="customer_display_name" {...register('customer_display_name')} />
      </div>

      <div className="space-y-2">
        <Label htmlFor="menu_item_id">Item</Label>
        <select
          id="menu_item_id"
          className="border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm"
          {...register('menu_item_id')}
        >
          <option value="">Select an item…</option>
          {menuItems?.map((item) => (
            <option key={item.menu_item_id} value={item.menu_item_id}>
              {item.name} (INR {item.price})
            </option>
          ))}
        </select>
        {errors.menu_item_id && (
          <p className="text-destructive text-sm">{errors.menu_item_id.message}</p>
        )}
        {menuItems?.length === 0 && (
          <p className="text-muted-foreground text-sm">Add a menu item in Catalog first.</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="quantity">Quantity</Label>
        <Input
          id="quantity"
          type="number"
          min={1}
          {...register('quantity', { valueAsNumber: true })}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="payment_method">Payment method</Label>
        <select
          id="payment_method"
          className="border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm"
          {...register('payment_method')}
        >
          <option value="online">Online (payment link)</option>
          <option value="cod">Cash on delivery/pickup</option>
        </select>
      </div>

      {checkout.isError && (
        <p className="text-destructive text-sm">Failed to create order. Please try again.</p>
      )}

      {checkout.isSuccess && checkout.data.payment_link_url && (
        <p className="text-sm">
          Payment link:{' '}
          <a
            href={checkout.data.payment_link_url}
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            {checkout.data.payment_link_url}
          </a>
        </p>
      )}
      {checkout.isSuccess && !checkout.data.payment_link_url && (
        <p className="text-sm">Order created and confirmed for COD.</p>
      )}

      <Button type="submit" disabled={checkout.isPending}>
        {checkout.isPending ? 'Creating…' : 'Create order'}
      </Button>
    </form>
  )
}
