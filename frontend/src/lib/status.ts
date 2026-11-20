import type { Status } from '../types'

export const STATUS_ORDER: Status[] = ['WORK', 'WEEKLY_OFF', 'HOLIDAY', 'LEAVE', 'COMP_OFF']
export const STATUS_META: Record<Status, { label: string; abbr: string }> = {
  WORK: { label: 'Working', abbr: 'W' },
  WEEKLY_OFF: { label: 'Weekly off', abbr: 'WO' },
  HOLIDAY: { label: 'Public holiday', abbr: 'H' },
  LEAVE: { label: 'Leave', abbr: 'L' },
  COMP_OFF: { label: 'Comp-off', abbr: 'CO' },
}
