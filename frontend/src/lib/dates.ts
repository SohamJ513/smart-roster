export function monthDays(year: number, month: number): string[] {
  const n = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const mm = String(month).padStart(2, '0')
  return Array.from({ length: n }, (_, i) => `${year}-${mm}-${String(i + 1).padStart(2, '0')}`)
}

/** Monday = 0 ... Sunday = 6, matching the backend. */
export function weekdayIndex(iso: string): number {
  return (new Date(`${iso}T00:00:00Z`).getUTCDay() + 6) % 7
}

export const dayNumber = (iso: string) => Number(iso.slice(8))

export function shortDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
}

export function monthLabel(year: number, month: number): string {
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })
}
