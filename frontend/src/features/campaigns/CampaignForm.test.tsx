import { describe, expect, it } from 'vitest'

import type { MessageTemplateOut } from '@/shared/api/types'

import { buildAudienceFilter, isTemplateSelectable, templateDisabledReason } from './CampaignForm'

function template(overrides: Partial<MessageTemplateOut> = {}): MessageTemplateOut {
  return {
    template_id: 't1',
    name: 'promo',
    category: 'MARKETING',
    language_code: 'en_US',
    header_type: 'NONE',
    header_text: null,
    header_media_handle: null,
    body_text: 'Hi',
    body_variable_count: 0,
    footer_text: null,
    buttons: [],
    meta_template_id: 'META1',
    meta_approval_status: 'pending',
    meta_rejection_reason: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('buildAudienceFilter', () => {
  it('maps "all" with no days field', () => {
    expect(
      buildAudienceFilter({
        name: 'x',
        template_id: 't1',
        audience_kind: 'all',
        schedule_kind: 'now',
      }),
    ).toEqual({ kind: 'all' })
  })

  it('maps ordered_within_days with the parsed day count', () => {
    expect(
      buildAudienceFilter({
        name: 'x',
        template_id: 't1',
        audience_kind: 'ordered_within_days',
        audience_days: '14',
        schedule_kind: 'now',
      }),
    ).toEqual({ kind: 'ordered_within_days', days: 14 })
  })

  it('maps no_order_within_days with the parsed day count', () => {
    expect(
      buildAudienceFilter({
        name: 'x',
        template_id: 't1',
        audience_kind: 'no_order_within_days',
        audience_days: '30',
        schedule_kind: 'now',
      }),
    ).toEqual({ kind: 'no_order_within_days', days: 30 })
  })
})

describe('isTemplateSelectable / templateDisabledReason', () => {
  it('only an approved template is selectable', () => {
    expect(isTemplateSelectable(template({ meta_approval_status: 'approved' }))).toBe(true)
    expect(isTemplateSelectable(template({ meta_approval_status: 'pending' }))).toBe(false)
    expect(isTemplateSelectable(template({ meta_approval_status: 'rejected' }))).toBe(false)
    expect(isTemplateSelectable(template({ meta_approval_status: 'paused' }))).toBe(false)
  })

  it('gives a distinct reason for pending vs rejected', () => {
    expect(templateDisabledReason(template({ meta_approval_status: 'pending' }))).toMatch(
      /awaiting/i,
    )
    expect(templateDisabledReason(template({ meta_approval_status: 'rejected' }))).toMatch(
      /rejected/i,
    )
  })
})
