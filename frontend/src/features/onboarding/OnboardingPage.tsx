import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCreateMenuItem } from '@/features/catalog/useCreateMenuItem'
import { useMenuItems } from '@/features/catalog/useMenuItems'
import {
  useKitchenProfile,
  useOnboardingStatus,
  useUpdateKitchenProfile,
} from '@/features/onboarding/useOnboarding'
import { TestWhatsAppMessageCard } from '@/features/settings/TestWhatsAppMessageCard'
import {
  useUpdateWhatsAppSettings,
  useWhatsAppSettings,
} from '@/features/settings/useWhatsAppSettings'
import type { OnboardingStatus } from '@/shared/api/types'

import { useOnboardingWizardStore } from './onboardingWizardStore'

const STEP_LABELS = ['Connect WhatsApp', 'Kitchen details', 'Add a menu item', 'Go live'] as const

// The wizard's displayed step is driven by Merchant.onboarding_status (the
// server-side source of truth, per IMPLEMENTATION_PLAN.md's Phase 8 note),
// not derived independently client-side.
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
    case 'live':
      return 3
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
    <ol className="flex flex-wrap gap-4 text-sm">
      {STEP_LABELS.map((label, index) => {
        const state = index < furthestReached ? 'done' : index === current ? 'active' : 'upcoming'
        const clickable = state === 'done' && index !== current
        return (
          <li key={label}>
            <button
              type="button"
              disabled={!clickable}
              onClick={() => onSelect(index)}
              className={`flex items-center gap-2 ${clickable ? 'cursor-pointer' : 'cursor-default'}`}
            >
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium transition-colors duration-150 ${
                  state === 'done'
                    ? 'bg-primary text-primary-foreground'
                    : state === 'active'
                      ? 'bg-brand-gold text-brand-gold-foreground'
                      : 'bg-muted text-muted-foreground'
                }`}
              >
                {state === 'done' ? '✓' : index + 1}
              </span>
              <span className={state === 'upcoming' ? 'text-muted-foreground' : 'font-medium'}>
                {label}
              </span>
            </button>
          </li>
        )
      })}
    </ol>
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
          <Label htmlFor="phone_number_id">Phone number ID</Label>
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
          <Label htmlFor="access_token">Access token</Label>
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
          {justSaved && !update.isPending && (
            <p className="flex items-center gap-1.5 text-sm font-medium text-green-700 dark:text-green-400">
              <span
                className="flex size-4 items-center justify-center rounded-full bg-green-600 text-[10px] text-white"
                aria-hidden
              >
                ✓
              </span>
              Saved and connected
            </p>
          )}
        </div>
      </form>
      {data?.access_token_set && <TestWhatsAppMessageCard />}
    </>
  )
}

const profileSchema = z.object({
  address_line1: z.string().min(1, 'Required'),
  address_line2: z.string().optional(),
  city: z.string().min(1, 'Required'),
  pincode: z.string().min(1, 'Required'),
  cuisine_type: z.string().min(1, 'Required'),
  fssai_license_no: z.string().optional(),
})
type ProfileForm = z.infer<typeof profileSchema>

function KitchenDetailsStep() {
  const { data } = useKitchenProfile()
  const update = useUpdateKitchenProfile()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    values: data
      ? {
          address_line1: data.address_line1 ?? '',
          address_line2: data.address_line2 ?? '',
          city: data.city ?? '',
          pincode: data.pincode ?? '',
          cuisine_type: data.cuisine_type ?? '',
          fssai_license_no: data.fssai_license_no ?? '',
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
        <Label htmlFor="cuisine_type">Cuisine type</Label>
        <Input
          id="cuisine_type"
          placeholder="North Indian, South Indian, ..."
          {...register('cuisine_type')}
        />
        {errors.cuisine_type && (
          <p className="text-destructive text-sm">{errors.cuisine_type.message}</p>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor="fssai_license_no">FSSAI license number (optional)</Label>
        <Input id="fssai_license_no" {...register('fssai_license_no')} />
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

const menuItemSchema = z.object({
  category: z.string().min(1, 'Required'),
  name: z.string().min(1, 'Required'),
  price: z
    .string()
    .min(1, 'Required')
    .refine((value) => !Number.isNaN(Number(value)) && Number(value) > 0, 'Enter a valid price'),
})
type MenuItemForm = z.infer<typeof menuItemSchema>

function AddMenuItemStep() {
  const { data: items } = useMenuItems()
  const createMenuItem = useCreateMenuItem()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<MenuItemForm>({ resolver: zodResolver(menuItemSchema) })

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
        onSubmit={handleSubmit((values) =>
          createMenuItem.mutate(values, { onSuccess: () => reset() }),
        )}
        className="space-y-4"
      >
        <div className="space-y-2">
          <Label htmlFor="category">Category</Label>
          <Input id="category" placeholder="Mains" {...register('category')} />
          {errors.category && <p className="text-destructive text-sm">{errors.category.message}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">Item name</Label>
          <Input id="name" placeholder="Butter Chicken" {...register('name')} />
          {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="price">Price</Label>
          <Input id="price" placeholder="349.00" {...register('price')} />
          {errors.price && <p className="text-destructive text-sm">{errors.price.message}</p>}
        </div>
        {createMenuItem.isError && (
          <p className="text-destructive text-sm">Failed to save. Please try again.</p>
        )}
        <Button type="submit" disabled={createMenuItem.isPending}>
          {createMenuItem.isPending ? 'Adding…' : 'Add item & go live'}
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
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Onboarding</h1>
        <p className="text-muted-foreground text-sm">
          Connect WhatsApp, add your kitchen details, and list at least one menu item to go live.
        </p>
      </div>

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
        {currentStep === 1 && <KitchenDetailsStep />}
        {currentStep === 2 && <AddMenuItemStep />}
        {currentStep === 3 && <LiveStep />}
      </Card>
    </div>
  )
}
