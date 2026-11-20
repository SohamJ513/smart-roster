import type { RosterData } from '../hooks/useRosterData'
import { summarize } from '../lib/summary'

export default function SummaryStrip({ data }: { data: RosterData }) {
  const s = summarize(data.issues, data.coverage)
  const pct = s.operatingDays ? Math.round((s.coveredDays / s.operatingDays) * 100) : 100
  const cards: { label: string; value: string; tone: 'good' | 'bad' | 'warn' | 'neutral'; note?: string }[] = [
    { label: 'Errors', value: String(s.errors), tone: s.errors ? 'bad' : 'good', note: s.errors ? 'must be fixed or acknowledged' : 'nothing blocking' },
    { label: 'Warnings', value: String(s.warnings), tone: s.warnings ? 'warn' : 'good', note: 'preferences and thin days' },
    { label: 'Coverage met', value: `${pct}%`, tone: s.coveredDays === s.operatingDays ? 'good' : 'bad', note: `${s.coveredDays} of ${s.operatingDays} process-days` },
    { label: 'Under minimum days off', value: String(s.underMinOff), tone: s.underMinOff ? 'bad' : 'good', note: 'people this month' },
  ]
  return (
    <ul className="summary" aria-label="Roster summary">
      {cards.map((c) => (
        <li key={c.label} className={`card stat ${c.tone}`}>
          <span className="stat-label">{c.label}</span>
          <strong>{c.value}</strong>
          {c.note && <small>{c.note}</small>}
        </li>
      ))}
    </ul>
  )
}