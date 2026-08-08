import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

/** Both ends optional and independent, matching the backend's
 * `from_date`/`to_date` query params exactly -- omitted means "all time" on
 * that side. Dates are plain `YYYY-MM-DD` strings (native `<input
 * type="date">` value format, and what the API expects). */
export type DateRangeValue = {
  from_date?: string
  to_date?: string
}

type DateRangePreset = 'today' | '7d' | '30d' | 'all'

const PRESETS: { key: DateRangePreset; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: '7d', label: 'Last 7 days' },
  { key: '30d', label: 'Last 30 days' },
  { key: 'all', label: 'All time' },
]

function toISODate(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function presetToRange(preset: DateRangePreset): DateRangeValue {
  if (preset === 'all') return {}
  const today = new Date()
  const to_date = toISODate(today)
  if (preset === 'today') return { from_date: to_date, to_date }
  const daysBack = preset === '7d' ? 6 : 29
  const from = new Date(today)
  from.setDate(from.getDate() - daysBack)
  return { from_date: toISODate(from), to_date }
}

function activePreset(value: DateRangeValue): DateRangePreset | 'custom' {
  if (!value.from_date && !value.to_date) return 'all'
  for (const preset of ['today', '7d', '30d'] as const) {
    const range = presetToRange(preset)
    if (range.from_date === value.from_date && range.to_date === value.to_date) return preset
  }
  return 'custom'
}

/** Preset buttons (Today / Last 7 days / Last 30 days / All time) plus two
 * native date inputs for a custom range. Fully controlled -- callers own
 * the `{ from_date, to_date }` state and decide what to do with it (drive a
 * query directly, or mirror it into URL search params). */
export function DateRangeFilter({
  value,
  onChange,
}: {
  value: DateRangeValue
  onChange: (next: DateRangeValue) => void
}) {
  const active = activePreset(value)

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap gap-1">
        {PRESETS.map((preset) => (
          <Button
            key={preset.key}
            type="button"
            size="sm"
            variant={active === preset.key ? 'default' : 'outline'}
            onClick={() => onChange(presetToRange(preset.key))}
          >
            {preset.label}
          </Button>
        ))}
      </div>
      <div className="flex items-center gap-1.5">
        <Input
          type="date"
          aria-label="From date"
          value={value.from_date ?? ''}
          max={value.to_date}
          onChange={(event) => onChange({ ...value, from_date: event.target.value || undefined })}
          className="h-8 w-[9.5rem] text-sm"
        />
        <span className="text-muted-foreground text-sm">to</span>
        <Input
          type="date"
          aria-label="To date"
          value={value.to_date ?? ''}
          min={value.from_date}
          onChange={(event) => onChange({ ...value, to_date: event.target.value || undefined })}
          className="h-8 w-[9.5rem] text-sm"
        />
      </div>
    </div>
  )
}
