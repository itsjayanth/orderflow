import { describe, expect, it } from 'vitest'

import { legalNextSubscriptionStatuses } from './subscriptionTransitions'

describe('legalNextSubscriptionStatuses', () => {
  it('offers only active from trialing', () => {
    expect(legalNextSubscriptionStatuses('trialing').sort()).toEqual(['active', 'expired'])
  })

  it('offers only past_due and canceled from active', () => {
    expect(legalNextSubscriptionStatuses('active').sort()).toEqual(['canceled', 'past_due'])
  })

  it('offers active and canceled from past_due', () => {
    expect(legalNextSubscriptionStatuses('past_due').sort()).toEqual(['active', 'canceled'])
  })

  it('offers only active from expired', () => {
    expect(legalNextSubscriptionStatuses('expired')).toEqual(['active'])
  })

  it('offers only active from canceled', () => {
    expect(legalNextSubscriptionStatuses('canceled')).toEqual(['active'])
  })
})
