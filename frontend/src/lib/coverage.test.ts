import { describe, expect, it } from 'vitest'
import { coverageCell } from './coverage'

describe('coverageCell', () => {
  it('is closed when nothing is required', () => expect(coverageCell(0, 0)).toBe('closed'))
  it('is a gap when fewer people work than required', () => expect(coverageCell(2, 1)).toBe('gap'))
  it('is thin when exactly the minimum of two or more works', () => expect(coverageCell(2, 2)).toBe('thin'))
  it('is ok with spare people', () => expect(coverageCell(2, 3)).toBe('ok'))
  it('treats a met single-person requirement as ok, not thin', () => expect(coverageCell(1, 1)).toBe('ok'))
  it('is a gap when nobody works a required day', () => expect(coverageCell(1, 0)).toBe('gap'))
})
