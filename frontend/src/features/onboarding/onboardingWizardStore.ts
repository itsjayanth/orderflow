import { create } from 'zustand'

// Client-only UI state for the onboarding wizard (which step is showing right
// now, before it's persisted). Server-side progress lives in
// Merchant.onboarding_status (ARCHITECTURE.md Section 5) and is fetched via
// TanStack Query, not duplicated here.
interface OnboardingWizardState {
  currentStep: number
  setStep: (step: number) => void
}

export const useOnboardingWizardStore = create<OnboardingWizardState>((set) => ({
  currentStep: 0,
  setStep: (step) => set({ currentStep: step }),
}))
