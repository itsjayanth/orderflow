import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ApiError } from '@/shared/api/client'

import { useCreateMenuItem } from './useCreateMenuItem'
import { useMenuItems } from './useMenuItems'
import { useUpdateMenuItem } from './useUpdateMenuItem'

const addItemSchema = z.object({
  category: z.string().min(1, 'Required'),
  name: z.string().min(1, 'Required'),
  price: z
    .string()
    .min(1, 'Required')
    .refine((value) => !Number.isNaN(Number(value)) && Number(value) > 0, 'Enter a valid price'),
})

type AddItemForm = z.infer<typeof addItemSchema>

export function CatalogPage() {
  const { data: items, isLoading } = useMenuItems()
  const createMenuItem = useCreateMenuItem()
  const updateMenuItem = useUpdateMenuItem()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AddItemForm>({ resolver: zodResolver(addItemSchema) })

  const onSubmit = (data: AddItemForm) => {
    createMenuItem.mutate(data, { onSuccess: () => reset() })
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Catalog</h1>
        <p className="text-muted-foreground text-sm">Menu/catalog management lives here.</p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Price</TableHead>
              <TableHead>Available</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground">
                  Loading…
                </TableCell>
              </TableRow>
            )}
            {!isLoading && items?.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground">
                  No menu items yet. Add one below.
                </TableCell>
              </TableRow>
            )}
            {items?.map((item) => (
              <TableRow key={item.menu_item_id}>
                <TableCell>{item.name}</TableCell>
                <TableCell>{item.category}</TableCell>
                <TableCell>{item.price}</TableCell>
                <TableCell>
                  <Switch
                    checked={item.is_available}
                    aria-label={`Toggle availability for ${item.name}`}
                    onCheckedChange={(checked) =>
                      updateMenuItem.mutate({
                        menu_item_id: item.menu_item_id,
                        is_available: checked,
                      })
                    }
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="max-w-md space-y-4 rounded-md border p-4">
        <h2 className="text-lg font-medium">Add item</h2>

        <div className="space-y-2">
          <Label htmlFor="category">Category</Label>
          <Input id="category" placeholder="Mains" {...register('category')} />
          {errors.category && <p className="text-destructive text-sm">{errors.category.message}</p>}
        </div>

        <div className="space-y-2">
          <Label htmlFor="name">Name</Label>
          <Input id="name" placeholder="Butter Chicken" {...register('name')} />
          {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
        </div>

        <div className="space-y-2">
          <Label htmlFor="price">Price</Label>
          <Input id="price" inputMode="decimal" placeholder="349.00" {...register('price')} />
          {errors.price && <p className="text-destructive text-sm">{errors.price.message}</p>}
        </div>

        {createMenuItem.isError && (
          <p className="text-destructive text-sm">
            {createMenuItem.error instanceof ApiError
              ? 'Something went wrong. Please try again.'
              : 'Something went wrong.'}
          </p>
        )}

        <Button type="submit" disabled={createMenuItem.isPending}>
          {createMenuItem.isPending ? 'Adding…' : 'Add item'}
        </Button>
      </form>
    </div>
  )
}
