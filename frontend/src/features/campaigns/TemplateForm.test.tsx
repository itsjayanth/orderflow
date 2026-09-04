import { describe, expect, it } from 'vitest'

import { MEDIA_HEADER_ACCEPT } from './TemplateForm'

describe('MEDIA_HEADER_ACCEPT', () => {
  it('narrows the file-input accept attribute per media header kind', () => {
    expect(MEDIA_HEADER_ACCEPT.IMAGE).toBe('image/jpeg,image/png')
    expect(MEDIA_HEADER_ACCEPT.VIDEO).toBe('video/mp4,video/3gpp')
    expect(MEDIA_HEADER_ACCEPT.DOCUMENT).toBe('application/pdf')
  })

  it('has no entry for NONE/TEXT -- those headers take no file upload', () => {
    expect(MEDIA_HEADER_ACCEPT.NONE).toBeUndefined()
    expect(MEDIA_HEADER_ACCEPT.TEXT).toBeUndefined()
  })
})
