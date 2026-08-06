import { describe, expect, it } from 'vitest'

import { legalNextStatuses } from './statusTransitions'

describe('legalNextStatuses', () => {
  it('offers preparing and cancelled from new', () => {
    expect(legalNextStatuses('new').sort()).toEqual(['cancelled', 'preparing'])
  })

  it('offers ready and cancelled from preparing', () => {
    expect(legalNextStatuses('preparing').sort()).toEqual(['cancelled', 'ready'])
  })

  it('offers completed and cancelled from ready', () => {
    expect(legalNextStatuses('ready').sort()).toEqual(['cancelled', 'completed'])
  })

  it('offers nothing from completed', () => {
    expect(legalNextStatuses('completed')).toEqual([])
  })

  it('offers nothing from cancelled', () => {
    expect(legalNextStatuses('cancelled')).toEqual([])
  })
})
