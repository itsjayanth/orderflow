import { zodResolver } from '@hookform/resolvers/zod'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { ApiError } from '@/shared/api/client'
import type { MenuItem } from '@/shared/api/types'
import { ItemImage } from '@/shared/components/ItemImage'
import { formatItemNumber } from '@/shared/lib/itemNumber'

import { useCreateMenuItem } from './useCreateMenuItem'
import { useMenuItems } from './useMenuItems'
import { useUpdateMenuItem } from './useUpdateMenuItem'

function matchesSearch(item: MenuItem, query: string): boolean {
  const q = query.trim().toLowerCase().replace(/^#/, '')
  if (!q) return true
  return (
    item.name.toLowerCase().includes(q) ||
    item.category.toLowerCase().includes(q) ||
    String(item.item_number).includes(q) ||
    formatItemNumber(item.item_number).toLowerCase().includes(q)
  )
}

type CategorySection = { category: string; items: MenuItem[] }

// One card per category, items kept in each category's first-appearance
// order -- the same grouping convention the customer-facing ordering
// webview uses for its menu (see OrderingPage.tsx's groupByCategory), so
// merchant and customer views read consistently.
function groupByCategory(items: MenuItem[]): CategorySection[] {
  const sections: CategorySection[] = []
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

const addItemSchema = z.object({
  category: z.string().min(1, 'Required'),
  name: z.string().min(1, 'Required'),
  price: z
    .string()
    .min(1, 'Required')
    .refine((value) => !Number.isNaN(Number(value)) && Number(value) > 0, 'Enter a valid price'),
  image_url: z
    .string()
    .trim()
    .optional()
    .refine((value) => !value || /^https?:\/\//i.test(value), 'Enter a valid image URL'),
})

type AddItemForm = z.infer<typeof addItemSchema>

function CatalogItemRow({
  item,
  onToggleAvailability,
  onSaveImageUrl,
}: {
  item: MenuItem
  onToggleAvailability: (checked: boolean) => void
  onSaveImageUrl: (imageUrl: string) => void
}) {
  const [editingImage, setEditingImage] = useState(false)
  const [imageDraft, setImageDraft] = useState(item.image_url ?? '')

  const startEditing = () => {
    setImageDraft(item.image_url ?? '')
    setEditingImage(true)
  }

  const save = () => {
    onSaveImageUrl(imageDraft.trim())
    setEditingImage(false)
  }

  return (
    <div className="flex flex-col gap-3 px-5 py-4">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => (editingImage ? setEditingImage(false) : startEditing())}
          aria-label={`Edit image for ${item.name}`}
          className="focus-visible:ring-ring/30 shrink-0 rounded-lg outline-none focus-visible:ring-4"
        >
          <ItemImage url={item.image_url} name={item.name} />
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-muted-foreground shrink-0 font-mono text-xs">
              {formatItemNumber(item.item_number)}
            </span>
            <p className="truncate font-medium">{item.name}</p>
          </div>
          <p className="text-muted-foreground text-sm">{item.price}</p>
        </div>

        <Switch
          checked={item.is_available}
          aria-label={`Toggle availability for ${item.name}`}
          onCheckedChange={onToggleAvailability}
        />
      </div>

      {editingImage && (
        <div className="border-border bg-muted/30 flex flex-wrap items-center gap-2 rounded-lg border border-dashed p-2 pl-[4rem]">
          <Input
            value={imageDraft}
            onChange={(e) => setImageDraft(e.target.value)}
            placeholder="https://example.com/photo.jpg"
            aria-label={`Image URL for ${item.name}`}
            className="h-8 flex-1 text-sm"
          />
          <Button type="button" size="sm" onClick={save}>
            Save
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => setEditingImage(false)}>
            Cancel
          </Button>
        </div>
      )}
    </div>
  )
}

export function CatalogPage() {
  const { data: items, isLoading } = useMenuItems()
  const createMenuItem = useCreateMenuItem()
  const updateMenuItem = useUpdateMenuItem()
  const [search, setSearch] = useState('')

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AddItemForm>({ resolver: zodResolver(addItemSchema) })

  const onSubmit = (data: AddItemForm) => {
    createMenuItem.mutate(
      { ...data, image_url: data.image_url || undefined },
      { onSuccess: () => reset() },
    )
  }

  const visibleItems = useMemo(
    () => items?.filter((item) => matchesSearch(item, search)) ?? [],
    [items, search],
  )

  const sections = useMemo(() => groupByCategory(visibleItems), [visibleItems])

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Catalog</h1>
        <p className="text-muted-foreground text-sm">
          Manage your menu items and control what customers can order.
        </p>
      </div>

      <Input
        type="search"
        placeholder="Search by item #, name, or category…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
        aria-label="Search menu items"
      />

      {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}

      {!isLoading && items?.length === 0 && (
        <Card className="p-6 text-center">
          <p className="text-muted-foreground text-sm">No menu items yet. Add one below.</p>
        </Card>
      )}

      {!isLoading && items && items.length > 0 && sections.length === 0 && (
        <Card className="p-6 text-center">
          <p className="text-muted-foreground text-sm">No items match "{search}".</p>
        </Card>
      )}

      <div className="space-y-6">
        {sections.map((section) => (
          <Card key={section.category} className="overflow-hidden py-0">
            <div className="border-border/60 flex items-baseline justify-between gap-3 border-b px-5 py-4">
              <h2 className="font-serif text-lg font-semibold">{section.category}</h2>
              <span className="text-muted-foreground text-xs">
                {section.items.length} item{section.items.length === 1 ? '' : 's'}
              </span>
            </div>
            <div className="divide-border/60 divide-y">
              {section.items.map((item) => (
                <CatalogItemRow
                  key={item.menu_item_id}
                  item={item}
                  onToggleAvailability={(checked) =>
                    updateMenuItem.mutate({
                      menu_item_id: item.menu_item_id,
                      is_available: checked,
                    })
                  }
                  onSaveImageUrl={(imageUrl) =>
                    updateMenuItem.mutate({
                      menu_item_id: item.menu_item_id,
                      image_url: imageUrl,
                    })
                  }
                />
              ))}
            </div>
          </Card>
        ))}
      </div>

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="bg-card max-w-md space-y-4 rounded-xl border p-4 shadow-sm"
      >
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

        <div className="space-y-2">
          <Label htmlFor="image_url">Image URL (optional)</Label>
          <Input
            id="image_url"
            placeholder="https://example.com/photo.jpg"
            {...register('image_url')}
          />
          {errors.image_url && (
            <p className="text-destructive text-sm">{errors.image_url.message}</p>
          )}
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
