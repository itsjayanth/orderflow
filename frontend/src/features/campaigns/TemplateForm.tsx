import { zodResolver } from '@hookform/resolvers/zod'
import { Plus, X } from 'lucide-react'
import { useState } from 'react'
import { Controller, useFieldArray, useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/shared/api/client'

import { useCreateTemplate } from './useTemplates'

// Mirrors backend/src/campaigns/domain/template_validation.py's rule:
// {{1}}, {{2}}, ... must be sequential starting at 1, no gaps/duplicates
// -- caught here so a merchant sees the problem before submitting, not
// only after a 422 comes back.
function variableNumbersAreSequential(body: string): boolean {
  const numbers = Array.from(body.matchAll(/\{\{(\d+)\}\}/g))
    .map((m) => Number(m[1]))
    .sort((a, b) => a - b)
  const expected = numbers.map((_, i) => i + 1)
  return JSON.stringify(numbers) === JSON.stringify(expected)
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      // dataURL is "data:<mime>;base64,<data>" -- only the payload after
      // the comma is what the backend's header_image_base64 field wants.
      const result = reader.result as string
      resolve(result.split(',')[1] ?? '')
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

const templateFormSchema = z
  .object({
    name: z.string().min(1, 'Required').max(512),
    category: z.enum(['MARKETING', 'UTILITY']),
    header_type: z.enum(['NONE', 'TEXT', 'IMAGE']),
    header_text: z.string().max(60).optional(),
    body_text: z.string().min(1, 'Required').max(1024).refine(variableNumbersAreSequential, {
      message: 'Variables must be {{1}}, {{2}}, ... in order, with no gaps.',
    }),
    footer_text: z.string().max(60).optional(),
    buttons: z.array(
      z.object({
        type: z.enum(['QUICK_REPLY', 'URL']),
        text: z.string().min(1, 'Required').max(25),
        url: z.string().optional(),
      }),
    ),
  })
  .refine((data) => data.header_type !== 'TEXT' || !!data.header_text?.trim(), {
    message: 'Header text is required for a text header.',
    path: ['header_text'],
  })

type TemplateFormValues = z.infer<typeof templateFormSchema>

export function TemplateForm() {
  const createTemplate = useCreateTemplate()
  // Kept out of react-hook-form's own state -- a File object isn't
  // serializable form data, it's a side input only read at submit time to
  // build header_image_base64.
  const [imageFile, setImageFile] = useState<File | null>(null)

  const {
    register,
    control,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<TemplateFormValues>({
    resolver: zodResolver(templateFormSchema),
    defaultValues: { category: 'MARKETING', header_type: 'NONE', buttons: [] },
  })
  const { fields, append, remove } = useFieldArray({ control, name: 'buttons' })
  const headerType = watch('header_type')
  const bodyText = watch('body_text') ?? ''
  const variableCount = new Set(Array.from(bodyText.matchAll(/\{\{(\d+)\}\}/g)).map((m) => m[1]))
    .size

  const onSubmit = async (data: TemplateFormValues) => {
    let headerImageBase64: string | undefined
    let headerImageContentType: string | undefined
    if (data.header_type === 'IMAGE' && imageFile) {
      headerImageBase64 = await fileToBase64(imageFile)
      headerImageContentType = imageFile.type
    }

    createTemplate.mutate(
      {
        name: data.name,
        category: data.category,
        header_type: data.header_type,
        header_text: data.header_type === 'TEXT' ? data.header_text : undefined,
        header_image_base64: headerImageBase64,
        header_image_content_type: headerImageContentType,
        body_text: data.body_text,
        footer_text: data.footer_text || undefined,
        buttons: data.buttons.map((b) => ({
          ...b,
          url: b.type === 'URL' ? (b.url ?? null) : null,
        })),
      },
      {
        onSuccess: () => {
          reset({ category: 'MARKETING', header_type: 'NONE', buttons: [] })
          setImageFile(null)
        },
      },
    )
  }

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>New template</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Template name</Label>
            <Input id="name" placeholder="e.g. Weekend Promo" {...register('name')} />
            {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="category">Category</Label>
            <Controller
              name="category"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="category" onBlur={field.onBlur}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="MARKETING">Marketing</SelectItem>
                    <SelectItem value="UTILITY">Utility</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="header_type">Header</Label>
            <Controller
              name="header_type"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="header_type" onBlur={field.onBlur}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="NONE">None</SelectItem>
                    <SelectItem value="TEXT">Text</SelectItem>
                    <SelectItem value="IMAGE">Image</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          {headerType === 'TEXT' && (
            <div className="space-y-2">
              <Label htmlFor="header_text">Header text</Label>
              <Input id="header_text" maxLength={60} {...register('header_text')} />
              {errors.header_text && (
                <p className="text-destructive text-sm">{errors.header_text.message}</p>
              )}
            </div>
          )}

          {headerType === 'IMAGE' && (
            <div className="space-y-2">
              <Label htmlFor="header_image">Header image</Label>
              <Input
                id="header_image"
                type="file"
                accept="image/jpeg,image/png"
                onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
              />
            </div>
          )}

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="body_text">Body</Label>
              <span className="text-muted-foreground text-xs">
                {variableCount} variable{variableCount === 1 ? '' : 's'}
              </span>
            </div>
            <Textarea
              id="body_text"
              rows={4}
              placeholder="Hi {{1}}, enjoy {{2}}% off this weekend only!"
              {...register('body_text')}
            />
            {errors.body_text && (
              <p className="text-destructive text-sm">{errors.body_text.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="footer_text">Footer (optional)</Label>
            <Input id="footer_text" maxLength={60} {...register('footer_text')} />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Buttons (optional)</Label>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => append({ type: 'QUICK_REPLY', text: '', url: '' })}
              >
                <Plus className="size-4" />
                Add button
              </Button>
            </div>
            {fields.map((field, index) => (
              <div key={field.id} className="flex flex-wrap items-start gap-2">
                <Controller
                  name={`buttons.${index}.type`}
                  control={control}
                  render={({ field: typeField }) => (
                    <Select value={typeField.value} onValueChange={typeField.onChange}>
                      <SelectTrigger className="w-36" aria-label={`Button ${index + 1} type`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="QUICK_REPLY">Quick reply</SelectItem>
                        <SelectItem value="URL">URL</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                />
                <Input
                  placeholder="Button text"
                  className="flex-1"
                  aria-label={`Button ${index + 1} text`}
                  {...register(`buttons.${index}.text`)}
                />
                {watch(`buttons.${index}.type`) === 'URL' && (
                  <Input
                    placeholder="https://example.com"
                    className="flex-1"
                    aria-label={`Button ${index + 1} URL`}
                    {...register(`buttons.${index}.url`)}
                  />
                )}
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`Remove button ${index + 1}`}
                  onClick={() => remove(index)}
                >
                  <X className="size-4" />
                </Button>
              </div>
            ))}
          </div>

          {createTemplate.isError && (
            <p className="text-destructive text-sm">
              {createTemplate.error instanceof ApiError
                ? createTemplate.error.message || 'Something went wrong. Please try again.'
                : 'Something went wrong.'}
            </p>
          )}

          <Button type="submit" disabled={createTemplate.isPending}>
            {createTemplate.isPending ? 'Submitting…' : 'Submit for approval'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
