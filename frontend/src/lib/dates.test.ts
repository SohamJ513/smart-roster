import { describe, expect, it } from 'vitest'
import { monthDays, weekdayIndex } from './dates'

describe('dates', () => {
  it('lists every day of a 28-day February', () => {
    const d = monthDays(2027, 2)
    expect(d).toHaveLength(28)
    expect(d[0]).toBe('2027-02-01')
    expect(d[27]).toBe('2027-02-28')
  })
  it('lists 31 days for December', () => expect(monthDays(2026, 12)).toHaveLength(31))
  it('numbers weekdays from Monday = 0 to Sunday = 6', () => {
    expect(weekdayIndex('2026-12-06')).toBe(6)
    expect(weekdayIndex('2026-12-07')).toBe(0)
  })
})
