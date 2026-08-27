import { zodResolver } from '@hookform/resolvers/zod'
import { Check, Info } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
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
import { Textarea } from '@/components/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useCreateItem } from '@/features/catalog/useCreateItem'
import { useItems } from '@/features/catalog/useItems'
import { useCreateFAQItem } from '@/features/faq/useCreateFAQItem'
import { useFAQItems } from '@/features/faq/useFAQItems'
import {
  useBusinessProfile,
  useOnboardingStatus,
  useUpdateBusinessProfile,
} from '@/features/onboarding/useOnboarding'
import { TestWhatsAppMessageCard } from '@/features/settings/TestWhatsAppMessageCard'
import {
  useUpdateWhatsAppSettings,
  useWhatsAppSettings,
} from '@/features/settings/useWhatsAppSettings'
import { cn } from '@/lib/utils'
import type { OnboardingStatus } from '@/shared/api/types'
import { PageHeader } from '@/shared/components/PageHeader'
import { SavedIndicator } from '@/shared/components/SavedIndicator'

import { useOnboardingWizardStore } from './onboardingWizardStore'

const STEP_LABELS = [
  'Connect WhatsApp',
  'Business details',
  'Add an item',
  'FAQs (optional)',
  'Go live',
] as const

// The wizard's displayed step is driven by Merchant.onboarding_status (the
// server-side source of truth, per IMPLEMENTATION_PLAN.md's Phase 8 note),
// not derived independently client-side. FAQs are a purely optional add-on
// with no server-side gate of their own (unlike every other step here) --
// `catalog_ready` still lands on it, but `live` skips straight past it, so
// nothing about reaching "live" ever depends on visiting this step.
function stepForStatus(status: OnboardingStatus): number {
  switch (status) {
    case 'registered':
    case 'meta_connected':
      return 0
    case 'whatsapp_verified':
      return 1
    case 'profile_completed':
      return 2
    case 'catalog_ready':
      return 3
    case 'live':
      return 4
  }
}

function Stepper({
  current,
  furthestReached,
  onSelect,
}: {
  current: number
  furthestReached: number
  onSelect: (step: number) => void
}) {
  return (
    <Card className="p-5 sm:p-6">
      <ol className="flex items-start">
        {STEP_LABELS.map((label, index) => {
          const state = index < furthestReached ? 'done' : index === current ? 'active' : 'upcoming'
          const clickable = state === 'done' && index !== current
          const isLast = index === STEP_LABELS.length - 1
          return (
            <li key={label} className={cn('flex items-start gap-2 sm:gap-3', !isLast && 'flex-1')}>
              <button
                type="button"
                disabled={!clickable}
                onClick={() => onSelect(index)}
                className={cn(
                  'flex flex-col items-center gap-2 text-center',
                  clickable ? 'cursor-pointer' : 'cursor-default',
                )}
              >
                <span
                  className={cn(
                    'flex size-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold shadow-sm transition-colors duration-150',
                    state === 'done'
                      ? 'bg-primary text-primary-foreground'
                      : state === 'active'
                        ? 'bg-brand-gold text-brand-gold-foreground ring-brand-gold/30 ring-4'
                        : 'bg-muted text-muted-foreground',
                  )}
                >
                  {state === 'done' ? <Check className="size-4" aria-hidden /> : index + 1}
                </span>
                <span
                  className={cn(
                    'w-20 text-xs leading-tight sm:w-24 sm:text-sm',
                    state === 'upcoming' ? 'text-muted-foreground' : 'text-foreground font-medium',
                  )}
                >
                  {label}
                </span>
              </button>
              {!isLast && (
                // mt-[17px] lines this up with the *circle's* vertical center
                // (size-9 = 36px tall, so half minus half the line's own
                // height), not the center of the whole button -- the button
                // is taller than the circle alone once the label wraps below
                // it, and centering against the full button would pull the
                // connector down off the circle.
                <div
                  className={cn(
                    'mt-[17px] h-0.5 flex-1 rounded-full transition-colors duration-150',
                    index < furthestReached ? 'bg-primary' : 'bg-border',
                  )}
                  aria-hidden
                />
              )}
            </li>
          )
        })}
      </ol>
    </Card>
  )
}

const whatsappSchema = z.object({
  phone_number_id: z.string().min(1, 'Required'),
  access_token: z.string().min(1, 'Required'),
  display_phone_number: z.string().optional(),
})
type WhatsAppForm = z.infer<typeof whatsappSchema>

function ConnectWhatsAppStep() {
  const { data } = useWhatsAppSettings()
  const update = useUpdateWhatsAppSettings()
  const [justSaved, setJustSaved] = useState(false)
  const {
    register,
    handleSubmit,
    resetField,
    formState: { errors },
  } = useForm<WhatsAppForm>({
    resolver: zodResolver(whatsappSchema),
    // Same reasoning as SettingsPage.tsx's WhatsAppSettingsSection: keeps
    // the phone number ID visible/editable across visits instead of a
    // blank field every time, which matters when re-pasting an expired
    // test token means coming back to this step repeatedly.
    values: {
      phone_number_id: data?.phone_number_id ?? '',
      display_phone_number: data?.display_phone_number ?? '',
      access_token: '',
    },
  })

  const onSubmit = (values: WhatsAppForm) => {
    update.mutate(values, {
      onSuccess: () => {
        resetField('access_token')
        setJustSaved(true)
        setTimeout(() => setJustSaved(false), 4000)
      },
    })
  }

  return (
    <>
      <form onSubmit={handleSubmit(onSubmit)} className="max-w-md space-y-4">
        <p className="text-muted-foreground text-sm">
          Paste your WhatsApp Business phone number ID and access token. Test/dummy values work fine
          for now -- switching to real credentials later doesn't require redoing this step.
        </p>
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <Label htmlFor="phone_number_id">Phone number ID</Label>
            <Tooltip>
              <TooltipTrigger>
                <Info
                  className="text-muted-foreground size-3.5"
                  aria-label="Phone number ID help"
                />
              </TooltipTrigger>
              <TooltipContent>
                Found on Meta's WhatsApp API Setup page, labeled "Phone number ID" -- not the phone
                number itself.
              </TooltipContent>
            </Tooltip>
          </div>
          <Input id="phone_number_id" {...register('phone_number_id')} />
          {errors.phone_number_id && (
            <p className="text-destructive text-sm">{errors.phone_number_id.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="display_phone_number">Display phone number (optional)</Label>
          <Input
            id="display_phone_number"
            placeholder="+91 90000 00000"
            {...register('display_phone_number')}
          />
        </div>
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <Label htmlFor="access_token">Access token</Label>
            <Tooltip>
              <TooltipTrigger>
                <Info className="text-muted-foreground size-3.5" aria-label="Access token help" />
              </TooltipTrigger>
              <TooltipContent>
                A permanent or temporary token generated for your WhatsApp Business app in Meta's
                developer console. Never pre-filled here -- re-paste it to rotate.
              </TooltipContent>
            </Tooltip>
          </div>
          <Input
            id="access_token"
            type="password"
            placeholder="Leave any value for now if you don't have a real token yet"
            {...register('access_token')}
          />
          {errors.access_token && (
            <p className="text-destructive text-sm">{errors.access_token.message}</p>
          )}
        </div>
        {update.isError && (
          <p className="text-destructive text-sm">Failed to save. Please try again.</p>
        )}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? 'Connecting…' : 'Connect & continue'}
          </Button>
          {justSaved && !update.isPending && <SavedIndicator message="Saved and connected" />}
        </div>
      </form>
      {data?.access_token_set && <TestWhatsAppMessageCard />}
    </>
  )
}

const BUSINESS_CATEGORY_OPTIONS = [
  'Restaurant',
  'Retail / Clothing',
  'Auto Parts',
  'Pharmacy',
  'Other',
] as const

const profileSchema = z.object({
  address_line1: z.string().min(1, 'Required'),
  address_line2: z.string().optional(),
  city: z.string().min(1, 'Required'),
  pincode: z.string().min(1, 'Required'),
  business_category: z.string().min(1, 'Required'),
  license_no: z.string().optional(),
})
type ProfileForm = z.infer<typeof profileSchema>

function BusinessDetailsStep() {
  const { data } = useBusinessProfile()
  const update = useUpdateBusinessProfile()
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    values: data
      ? {
          address_line1: data.address_line1 ?? '',
          address_line2: data.address_line2 ?? '',
          city: data.city ?? '',
          pincode: data.pincode ?? '',
          business_category: data.business_category ?? '',
          license_no: data.license_no ?? '',
        }
      : undefined,
  })

  return (
    <form onSubmit={handleSubmit((values) => update.mutate(values))} className="max-w-md space-y-4">
      <div className="space-y-2">
        <Label htmlFor="address_line1">Address line 1</Label>
        <Input id="address_line1" {...register('address_line1')} />
        {errors.address_line1 && (
          <p className="text-destructive text-sm">{errors.address_line1.message}</p>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor="address_line2">Address line 2 (optional)</Label>
        <Input id="address_line2" {...register('address_line2')} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="city">City</Label>
          <Input id="city" {...register('city')} />
          {errors.city && <p className="text-destructive text-sm">{errors.city.message}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="pincode">Pincode</Label>
          <Input id="pincode" {...register('pincode')} />
          {errors.pincode && <p className="text-destructive text-sm">{errors.pincode.message}</p>}
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="business_category">Business category</Label>
        <Controller
          name="business_category"
          control={control}
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger id="business_category" onBlur={field.onBlur}>
                <SelectValue placeholder="Select a category…" />
              </SelectTrigger>
              <SelectContent>
                {BUSINESS_CATEGORY_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
        {errors.business_category && (
          <p className="text-destructive text-sm">{errors.business_category.message}</p>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor="license_no">License number (optional)</Label>
        <Input id="license_no" {...register('license_no')} />
      </div>
      {update.isError && (
        <p className="text-destructive text-sm">Failed to save. Please try again.</p>
      )}
      <Button type="submit" disabled={update.isPending}>
        {update.isPending ? 'Saving…' : 'Save & continue'}
      </Button>
    </form>
  )
}

const itemSchema = z.object({
  category: z.string().min(1, 'Required'),
  name: z.string().min(1, 'Required'),
  price: z
    .string()
    .min(1, 'Required')
    .refine((value) => !Number.isNaN(Number(value)) && Number(value) > 0, 'Enter a valid price'),
})
type ItemForm = z.infer<typeof itemSchema>

function AddItemStep() {
  const { data: items } = useItems()
  const createItem = useCreateItem()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ItemForm>({ resolver: zodResolver(itemSchema) })

  return (
    <div className="max-w-md space-y-4">
      <p className="text-muted-foreground text-sm">
        Add at least one item so customers have something to order. You can add the rest later from
        the Catalog page.
      </p>
      {items && items.length > 0 && (
        <p className="text-sm">
          {items.length} item{items.length === 1 ? '' : 's'} already on your menu.
        </p>
      )}
      <form
        onSubmit={handleSubmit((values) => createItem.mutate(values, { onSuccess: () => reset() }))}
        className="space-y-4"
      >
        <div className="space-y-2">
          <Label htmlFor="category">Category</Label>
          <Input id="category" placeholder="e.g. Category" {...register('category')} />
          {errors.category && <p className="text-destructive text-sm">{errors.category.message}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">Item name</Label>
          <Input id="name" placeholder="e.g. Product name" {...register('name')} />
          {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="price">Price</Label>
          <Input id="price" placeholder="349.00" {...register('price')} />
          {errors.price && <p className="text-destructive text-sm">{errors.price.message}</p>}
        </div>
        {createItem.isError && (
          <p className="text-destructive text-sm">Failed to save. Please try again.</p>
        )}
        <Button type="submit" disabled={createItem.isPending}>
          {createItem.isPending ? 'Adding…' : 'Add item & go live'}
        </Button>
      </form>
    </div>
  )
}

const FAQ_PLACEHOLDER_PROMPTS = [
  'Where are you located?',
  'What are your timings?',
  'What do you recommend?',
]

const faqItemSchema = z.object({
  question_text: z.string().min(1, 'Required'),
  answer_text: z.string().min(1, 'Required'),
  keywords: z.string().optional(),
})
type FAQItemForm = z.infer<typeof faqItemSchema>

function AddFAQStep() {
  const { data: items } = useFAQItems()
  const createFAQItem = useCreateFAQItem()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FAQItemForm>({ resolver: zodResolver(faqItemSchema) })

  const onSubmit = (values: FAQItemForm) => {
    createFAQItem.mutate(
      {
        question_text: values.question_text,
        answer_text: values.answer_text,
        keywords: (values.keywords ?? '')
          .split(',')
          .map((keyword) => keyword.trim())
          .filter(Boolean),
      },
      { onSuccess: () => reset() },
    )
  }

  return (
    <div className="max-w-md space-y-4">
      <p className="text-muted-foreground text-sm">
        Add answers to questions customers often ask on WhatsApp -- the bot replies automatically
        when it recognizes one. This step is entirely optional and won't hold up going live; add as
        many or as few as you like now, or manage them anytime from the FAQs page.
      </p>
      {items && items.length > 0 ? (
        <ul className="space-y-1 text-sm">
          {items.map((item) => (
            <li key={item.faq_item_id} className="text-muted-foreground">
              {item.question_text}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground text-sm">
          For example: "{FAQ_PLACEHOLDER_PROMPTS.join('", "')}"
        </p>
      )}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="question_text">Question</Label>
          <Input
            id="question_text"
            placeholder={FAQ_PLACEHOLDER_PROMPTS[0]}
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
          <Input id="keywords" placeholder="location, address, where" {...register('keywords')} />
        </div>
        {createFAQItem.isError && (
          <p className="text-destructive text-sm">Failed to save. Please try again.</p>
        )}
        <Button type="submit" disabled={createFAQItem.isPending}>
          {createFAQItem.isPending ? 'Adding…' : 'Add another'}
        </Button>
      </form>
    </div>
  )
}

function LiveStep() {
  return (
    <div className="max-w-md space-y-3">
      <span className="bg-primary text-primary-foreground flex size-10 items-center justify-center rounded-full text-lg">
        ✓
      </span>
      <p className="font-serif text-lg font-medium">You're live!</p>
      <p className="text-muted-foreground text-sm">
        Customers can now message your WhatsApp number to browse the menu and place orders. Incoming
        orders will show up on the Orders page.
      </p>
    </div>
  )
}

export function OnboardingPage() {
  const { data: status, isLoading } = useOnboardingStatus()
  const currentStep = useOnboardingWizardStore((s) => s.currentStep)
  const setStep = useOnboardingWizardStore((s) => s.setStep)

  const serverStep = status ? stepForStatus(status.onboarding_status) : 0

  // Auto-advance the displayed step whenever server progress newly moves
  // past where it was last seen -- but only fire once per such change (keyed
  // on serverStep itself, not on currentStep) so a merchant clicking back
  // into a completed step to review/edit it doesn't get immediately snapped
  // forward again by this same effect re-running.
  const lastSeenServerStep = useRef(serverStep)
  useEffect(() => {
    if (serverStep > lastSeenServerStep.current) {
      setStep(serverStep)
    }
    lastSeenServerStep.current = serverStep
  }, [serverStep, setStep])

  if (isLoading || !status) {
    return <p className="text-muted-foreground text-sm">Loading…</p>
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Onboarding"
        description="Connect WhatsApp, add your business details, and list at least one item to go live. FAQs are optional."
      />

      <Stepper current={currentStep} furthestReached={serverStep} onSelect={setStep} />

      <Card className="p-6">
        {currentStep < serverStep && (
          <div className="bg-muted mb-4 flex items-center justify-between rounded-lg p-3 text-sm">
            <span>This step is already done -- you're editing it.</span>
            <Button variant="ghost" size="sm" onClick={() => setStep(serverStep)}>
              Back to current step
            </Button>
          </div>
        )}
        {currentStep === 0 && <ConnectWhatsAppStep />}
        {currentStep === 1 && <BusinessDetailsStep />}
        {currentStep === 2 && <AddItemStep />}
        {currentStep === 3 && <AddFAQStep />}
        {currentStep === 4 && <LiveStep />}
      </Card>
    </div>
  )
}
