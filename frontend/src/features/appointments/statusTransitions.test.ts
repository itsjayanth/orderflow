import { describe, expect, it } from 'vitest'

import { legalNextStatuses } from './statusTransitions'

describe('legalNextStatuses', () => {
  it('offers confirmed and cancelled from requested', () => {
    expect(legalNextStatuses('requested').sort()).toEqual(['cancelled', 'confirmed'])
  })

  it('offers completed and cancelled from confirmed', () => {
    expect(legalNextStatuses('confirmed').sort()).toEqual(['cancelled', 'completed'])
  })

  it('offers nothing from completed', () => {
    expect(legalNextStatuses('completed')).toEqual([])
  })

  it('offers nothing from cancelled', () => {
    expect(legalNextStatuses('cancelled')).toEqual([])
  })
})
