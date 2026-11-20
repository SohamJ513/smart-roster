import { describe, expect, it } from 'vitest'
import { buildQuery } from './api'

describe('buildQuery', () => {
  it('joins params in order', () => {
    expect(buildQuery({ date: '2026-12-05', process_id: 3 })).toBe('date=2026-12-05&process_id=3')
  })
  it('skips undefined values and encodes text', () => {
    expect(buildQuery({ code: 'NO COVERAGE', gone: undefined })).toBe('code=NO%20COVERAGE')
  })
})
