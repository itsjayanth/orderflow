import { describe, expect, it } from 'vitest'

import { formatPhoneNumber } from './phoneNumber'

describe('formatPhoneNumber', () => {
  it('splits raw country-code-plus-number digits with a leading + and grouped local number', () => {
    expect(formatPhoneNumber('919876543210')).toBe('+91 98765 43210')
  })

  it('strips stray characters (spaces, dashes, an existing +) before reformatting', () => {
    expect(formatPhoneNumber('+91-98765 43210')).toBe('+91 98765 43210')
    expect(formatPhoneNumber('91 9876 543 210')).toBe('+91 98765 43210')
  })

  it('handles a longer country code (more than 2 digits)', () => {
    // e.g. a 3-digit country code + 10-digit local number = 13 digits.
    expect(formatPhoneNumber('2519876543210')).toBe('+251 98765 43210')
  })

  it('falls back to returning the input unchanged when it has too few digits to contain a country code', () => {
    expect(formatPhoneNumber('12345')).toBe('12345')
    expect(formatPhoneNumber('9876543210')).toBe('9876543210')
  })

  it('falls back to returning the input unchanged when it has implausibly many digits', () => {
    const tooLong = '1234567890123456'
    expect(formatPhoneNumber(tooLong)).toBe(tooLong)
  })

  it('falls back to returning the input unchanged for empty/non-numeric input', () => {
    expect(formatPhoneNumber('')).toBe('')
    expect(formatPhoneNumber('not-a-number')).toBe('not-a-number')
  })
})
