import { zodResolver } from '@hookform/resolvers/zod'
import { HelpCircle } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/shared/api/client'
import type { FAQItemOut } from '@/shared/api/types'
import { EmptyState } from '@/shared/components/EmptyState'
import { PageHeader } from '@/shared/components/PageHeader'

import { useCreateFAQItem } from './useCreateFAQItem'
import { useFAQItems } from './useFAQItems'
import { useUpdateFAQItem } from './useUpdateFAQItem'

function parseKeywords(raw: string): string[] {
  return raw
    .split(',')
    .map((keyword) => keyword.trim())
    .filter(Boolean)
}

const addFAQSchema = z.object({
  question_text: z.string().min(1, 'Required'),
  answer_text: z.string().min(1, 'Required'),
  keywords: z.string().optional(),
})

type AddFAQForm = z.infer<typeof addFAQSchema>

function FAQItemRow({
  item,
  onToggleActive,
  onSave,
}: {
  item: FAQItemOut
  onToggleActive: (checked: boolean) => void
  onSave: (input: { question_text: string; answer_text: string; keywords: string[] }) => void
}) {
  const [editing, setEditing] = useState(false)
  const [questionDraft, setQuestionDraft] = useState(item.question_text)
  const [answerDraft, setAnswerDraft] = useState(item.answer_text)
  const [keywordsDraft, setKeywordsDraft] = useState(item.keywords.join(', '))

  const startEditing = () => {
    setQuestionDraft(item.question_text)
    setAnswerDraft(item.answer_text)
    setKeywordsDraft(item.keywords.join(', '))
    setEditing(true)
  }

  const save = () => {
    onSave({
      question_text: questionDraft.trim(),
      answer_text: answerDraft.trim(),
      keywords: parseKeywords(keywordsDraft),
    })
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="space-y-3 px-5 py-4">
        <div className="space-y-2">
          <Label htmlFor={`question-${item.faq_item_id}`}>Question</Label>
          <Input
            id={`question-${item.faq_item_id}`}
            value={questionDraft}
            onChange={(e) => setQuestionDraft(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={`answer-${item.faq_item_id}`}>Answer</Label>
          <Textarea
            id={`answer-${item.faq_item_id}`}
            value={answerDraft}
            onChange={(e) => setAnswerDraft(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={`keywords-${item.faq_item_id}`}>Keywords (comma-separated)</Label>
          <Input
            id={`keywords-${item.faq_item_id}`}
            value={keywordsDraft}
            onChange={(e) => setKeywordsDraft(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <Button type="button" size="sm" onClick={save}>
            Save
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 px-5 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-medium">{item.question_text}</p>
          <p className="text-muted-foreground text-sm">{item.answer_text}</p>
          {item.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {item.keywords.map((keyword) => (
                <Badge key={keyword} tone="gray">
                  {keyword}
                </Badge>
              ))}
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-label={`Edit ${item.question_text}`}
            onClick={startEditing}
          >
            Edit
          </Button>
          <Switch
            checked={item.is_active}
            aria-label={`Toggle active for ${item.question_text}`}
            onCheckedChange={onToggleActive}
          />
        </div>
      </div>
    </div>
  )
}

function FAQItemRowSkeleton() {
  return (
    <div className="space-y-2 px-5 py-4">
      <Skeleton className="h-4 w-64" />
      <Skeleton className="h-3 w-full" />
    </div>
  )
}

export function FAQPage() {
  const { data: items, isLoading } = useFAQItems()
  const createFAQItem = useCreateFAQItem()
  const updateFAQItem = useUpdateFAQItem()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AddFAQForm>({ resolver: zodResolver(addFAQSchema) })

  const onSubmit = (data: AddFAQForm) => {
    createFAQItem.mutate(
      {
        question_text: data.question_text,
        answer_text: data.answer_text,
        keywords: parseKeywords(data.keywords ?? ''),
      },
      { onSuccess: () => reset() },
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="FAQs"
        description="Answers the WhatsApp bot sends automatically when a customer asks a matching question."
      />

      {isLoading && (
        <Card className="overflow-hidden py-0">
          <div className="divide-border/60 divide-y">
            <FAQItemRowSkeleton />
            <FAQItemRowSkeleton />
          </div>
        </Card>
      )}

      {!isLoading && items?.length === 0 && (
        <EmptyState icon={HelpCircle} title="No FAQs yet. Add one below." />
      )}

      {!isLoading && items && items.length > 0 && (
        <Card className="overflow-hidden py-0">
          <div className="divide-border/60 divide-y">
            {items.map((item) => (
              <FAQItemRow
                key={item.faq_item_id}
                item={item}
                onToggleActive={(checked) =>
                  updateFAQItem.mutate({ faq_item_id: item.faq_item_id, is_active: checked })
                }
                onSave={(input) =>
                  updateFAQItem.mutate({ faq_item_id: item.faq_item_id, ...input })
                }
              />
            ))}
          </div>
        </Card>
      )}

      <Card className="max-w-md">
        <CardHeader>
          <CardTitle>Add FAQ</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="question_text">Question</Label>
              <Input
                id="question_text"
                placeholder="Where are you located?"
                {...register('question_text')}
              />
              {errors.question_text && (
                <p className="text-destructive text-sm">{errors.question_text.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="answer_text">Answer</Label>
              <Textarea
                id="answer_text"
                placeholder="We're at 12 MG Road, Bengaluru."
                {...register('answer_text')}
              />
              {errors.answer_text && (
                <p className="text-destructive text-sm">{errors.answer_text.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="keywords">Keywords (comma-separated, optional)</Label>
              <Input
                id="keywords"
                placeholder="location, address, where"
                {...register('keywords')}
              />
            </div>

            {createFAQItem.isError && (
              <p className="text-destructive text-sm">
                {createFAQItem.error instanceof ApiError
                  ? 'Something went wrong. Please try again.'
                  : 'Something went wrong.'}
              </p>
            )}

            <Button type="submit" disabled={createFAQItem.isPending}>
              {createFAQItem.isPending ? 'Adding…' : 'Add FAQ'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
