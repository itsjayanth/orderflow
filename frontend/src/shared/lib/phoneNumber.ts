// Customer WhatsApp numbers are stored as raw digits -- country code and
// subscriber number concatenated with no separator (e.g. "919876543210")
// -- because that's the shape the WhatsApp Cloud API sends/expects. This
// is purely a display concern: format for the merchant dashboard without
// touching how the number is stored or sent anywhere else.
export function formatPhoneNumber(raw: string): string {
  const digits = raw.replace(/\D/g, '')

  // A country code plus a real subscriber number needs at least 11 digits
  // (1-digit country code + 10-digit number); E.164 numbers top out at 15
  // digits total. Outside that range we can't confidently split off a
  // country code, so don't guess -- show the original input untouched.
  if (digits.length < 11 || digits.length > 15) {
    return raw
  }

  // Assume a 10-digit local number (true for India, our pilot market, and
  // a reasonable default elsewhere) with whatever remains as the country
  // code.
  const localNumber = digits.slice(-10)
  const countryCode = digits.slice(0, -10)
  const groupedLocalNumber = `${localNumber.slice(0, 5)} ${localNumber.slice(5)}`

  return `+${countryCode} ${groupedLocalNumber}`
}
