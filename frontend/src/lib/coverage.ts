export type CoverageState = 'ok' | 'thin' | 'gap' | 'closed'

/** How a process-day should look: required vs working people. */
export function coverageCell(required: number, working: number): CoverageState {
  if (required <= 0) return 'closed'
  if (working < required) return 'gap'
  if (working === required && required >= 2) return 'thin'
  return 'ok'
}
