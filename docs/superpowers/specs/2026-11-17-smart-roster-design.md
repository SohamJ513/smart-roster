# Smart Roster Management System: Design

Date: 2026-11-17
Status: Draft, awaiting approval
Source: DataStraw Tech Internship Assessment (7-page PDF). Submission due 4 days from receipt, about 1.5-2 days of focused work.

## 1. Intent and why

This is a hiring assessment. DataStraw wants a deployed web app where an operations manager plans, generates, validates and edits a monthly roster for 30+ employees across brands, processes and pods. The assessment says plainly that reliable scheduling and clear conflict detection are worth more than a polished UI, and that it is not a calendar or a digitised spreadsheet.

The author must also be able to explain the system. The README has to answer eight "how do you think" questions, so every design choice below needs a reason that can be said out loud.

Deliverables: public URL with realistic sample data, GitHub repo (README, setup steps, `.env.example`), a 3-5 minute demo video, an approach note, and the author's LinkedIn link.

## 2. Goals, non-goals, anti-goals

**Goals**
- Central database of employees, pods, pod leads, brands, processes and assignments, all editable in the UI with no code change.
- Configurable operating rules and minimum coverage per process, including per-weekday and per-date overrides.
- Per-employee availability: weekly offs, planned leaves, comp-offs, preferences. A shared public-holiday calendar.
- Generate a monthly roster; validate any roster (generated or hand-edited) and list every issue with a plain-English reason.
- Five views: company, pod, brand, process, employee.
- Manual edits that are validated immediately.
- A change flow: after a roster exists, a leave or availability change shows the coverage gaps it causes and suggests fixes.
- 30+ employees, roughly 25 brands, sample data with realistic staffing patterns.

**Non-goals**
- Hours, payroll, overtime pay, or shift-by-shift headcount.
- Login, roles and permissions, multi-tenant support. The app is a single-manager demo and the README says so.
- Email or push notifications.
- Approval workflows beyond draft to published.
- Hosted AI features. Conflict explanations are generated from templates.

**Anti-goals (a failure even if it technically runs)**
- Silently producing a roster that breaks a hard rule.
- Showing "infeasible" or an empty roster without saying which day, process and reason.
- Hard-coding any brand's rules in code.
- A roster that looks full but double-counts one person across incompatible work.

## 3. Constraints

- Four-day deadline. Scope is cut to the core first, extras last (see section 9).
- Publicly accessible with no local setup.
- Stack is the author's choice. Chosen below.
- Not everything needed for a valid roster is given. Assumptions must be documented and the relevant values configurable.

## 4. Approaches considered

**Stack (decided by the author)**

| Option | Trade-off | Result |
|---|---|---|
| A. FastAPI + OR-Tools CP-SAT + React (Vite) + SQL database, one deployable service | Real optimizer, honest answers about feasibility; more setup | **Chosen** |
| B. Next.js full-stack TypeScript with a hand-written greedy-plus-repair scheduler | One language, one fast deploy; heuristic is harder to defend on correctness | Rejected |
| C. Python only with server-rendered pages | Fastest to build; the roster grid with inline edits would be clunky | Rejected |

**Scheduling approach.** A constraint solver with slack variables on coverage, plus an independent validator. Rejected alternatives: pure greedy (cannot prove a result is best, struggles with weekly-off fairness) and a solver without a separate validator (manual edits would have no safety net).

**Shifts (decided by the author).** The core roster is day-level (working, off, leave, holiday). Each process has an optional shift label with start and end times. Most processes are "General" with no time window. The validator flags an employee assigned to two processes with overlapping explicit windows on the same day. This is the author's reading of "incompatible shifts" in section 3.D of the assessment. A full morning/evening roster model was rejected as unrequested complexity.

## 5. Data model

Plain relational tables so new brands, processes and employees need no schema change.

- **pod**: id, name, lead_employee_id.
- **employee**: id, name, pod_id, weekly_off_mode (`fixed` or `flexible`), fixed_weekday (nullable), preferred_off_weekday (nullable, soft), active.
- **brand**: id, name, default operating rule (processes may override).
- **process**: id, brand_id, name (CS, ACC, NDR, Retention, ...), operating_rule, min_staff_default, shift_label, shift_start and shift_end (nullable).
- **operating_rule** is a small structure: `weekdays` (set of 0-6) and `holidays_off` (bool). The three named patterns from the assessment are presets of this: 365 days (all weekdays, holidays_off false), daily except holidays (all weekdays, true), Sundays and holidays off (Mon-Sat, true).
- **coverage_override**: process_id, weekday or specific date, min_staff. Covers "minimum staffing on specific days".
- **assignment**: employee_id, process_id, role (`primary` or `backup`). Many-to-many. A single-resource brand is one employee holding every process of that brand; a multi-employee brand spreads or overlaps them. No special-casing.
- **holiday**: date, name. One shared calendar.
- **leave**: employee_id, date, type (`planned` or `comp_off`), status (`approved`).
- **roster**: id, month, status (`draft` or `published`), version.
- **roster_entry**: roster_id, employee_id, date, status (`WORK`, `WEEKLY_OFF`, `HOLIDAY`, `LEAVE`, `COMP_OFF`), locked (bool), source (`solver` or `manual`).
- Issues are computed, not stored.

The operating calendar (a process property) and the employee schedule (roster entries) are separate on purpose, as the assessment asks.

## 6. Scheduling logic

**Coverage definition.** On a day when a process operates, the number of employees with status WORK who hold a primary assignment to it must be at least the required minimum (default or override). A working employee counts toward every process they are assigned to, except where explicit shift windows overlap: then they count for at most one of those processes that day, and the solver chooses which. "General" processes (no window) never conflict.

**Hard constraints (must hold)**
1. Coverage met on every operating day for every process.
2. Employees on approved leave or comp-off are not WORK.
3. No more than 6 consecutive working days, and at least 4 non-working days in the month beyond holidays (configurable).
4. One status per employee per day. Locked entries are respected.
5. No double-counting across overlapping explicit shift windows.

**Soft constraints (preferences, in priority order)**
1. Preferred weekly-off weekday honoured where possible.
2. Fair spread of Sunday and holiday work across employees.
3. Fewer days with thin coverage (coverage exactly at minimum).

**Priority.** Required coverage always beats a preferred weekly off. If a fixed weekly off would uncover a process, that is reported as a conflict instead of being silently dropped.

**Solver.** OR-Tools CP-SAT, one boolean per (employee, date). Coverage uses a slack variable with a very large penalty, so the solver always returns a roster plus an explicit shortfall list (process, date, needed, available, reason) instead of "infeasible". Objective = shortfall penalty >> preference penalties >> fairness penalties. Time limit around 10 seconds.

**Validator.** Independent plain-Python function over any roster. Returns:
- ERROR (hard): no assigned employee available on a required day, insufficient staffing, rest-rule breach, overlapping shift windows, work on leave.
- WARNING (soft): preference violated, thin coverage, uneven holiday work.

Each issue carries date, process or employee, severity, and a message that says what needs attention. The same validator checks solver output, so a solver bug cannot hide a bad roster.

## 7. Handling changes

Entry points: add or remove a leave, change an employee's availability, change a process requirement.

1. The change is applied to the working roster and the validator runs. The UI shows new and resolved issues side by side (before and after).
2. Single-resource case: if the only assigned employee becomes unavailable on a required day, the result is an ERROR gap with a clear message. Multi-employee case: the validator evaluates whether the remaining employees still meet the minimum, and reports a gap only if they do not.
3. For each gap, the app suggests fixes, each shown with its impact:
   - **Backup candidates**: employees in the same pod (then other pods) who are free that day, within rest limits, and do not create a shift conflict. Ranked by same-process experience, then lowest current workload.
   - **Swap**: move a weekly off of an assigned employee to another day where coverage still holds.
   - **Partial re-solve**: re-run the solver on a window of about 7 days around the gap, with everything outside it locked.
4. The manager picks one; it is applied as a manual entry and re-validated. Nothing changes without their action.

## 8. Interface and API

**Views** (all read the same roster): company grid (employees by days, status chips, a coverage strip along the top); pod; brand (processes by days, count versus required, who is working); process; employee calendar. A side panel lists issues with severity filter and click-to-jump. Cell edits call validation and show the delta.

**Config screens** for pods, employees, brands, processes, assignments, holidays, leaves, rules and overrides. Forms only; no code changes needed.

**Publish rule**: a roster with any ERROR cannot be published unless the manager explicitly acknowledges the listed gaps; the acknowledgement is recorded.

**API (FastAPI)**: CRUD for each table; `POST /rosters/generate`; `GET /rosters/{id}/validate`; `PATCH /rosters/{id}/entries`; `POST /rosters/{id}/impact` (what-if for a leave); `GET /rosters/{id}/suggestions`; `POST /rosters/{id}/publish`; `GET /rosters/{id}/export.csv`.

**Frontend**: React with Vite and TypeScript, TanStack Query for data. Styling kept simple and consistent.

## 9. Scope order for four days

1. Day 1: data model, seed data, validator with tests.
2. Day 2: solver, generate and validate endpoints, change-impact logic.
3. Day 3: config screens, the five views, editing with live validation, the change flow with suggestions.
4. Day 4: deployment, README (including the eight answers), demo video, approach note.

Extras, in order, only if time allows: CSV export, fairness tuning, comparison of two alternative rosters, lightweight approval status. Anything else is cut.

## 10. Sample data

- 32-34 employees, 4 pods each with a lead who is also an employee, about 25 brands.
- About 80% of brands (20) are single-resource. A few employees hold two small brands.
- The remaining 5 brands have 2-3 employees: some with separate processes (CS, ACC, NDR), some with overlap, and at least two processes that need two people.
- Operating rules cover all three presets; at least one brand has one 7-day process and one that follows a different calendar.
- One or two brands have processes with explicit Morning and Evening windows so the shift rule is demonstrable.
- Public holidays for the demo months, plus a few planned leaves and a comp-off.
- A prepared demo scenario: a roster generated for the demo month, then one single-resource employee's leave added to show the gap and the suggestions.

## 11. Deployment

One service: FastAPI serves the API and the built React files. SQLAlchemy with `DATABASE_URL`: SQLite for the demo, PostgreSQL as the stated scaling path. Dockerfile for hosting on Render, Railway or Fly. Seed runs on first start when the database is empty, and a "Reset demo data" button restores it. The README notes that free tiers may sleep, so the first load can be slow.

## 12. Assumptions (the author's calls, to be listed in the README)

- Single daily status, not hours; optional shift labels only for the overlap rule.
- Six-day maximum work run; configurable.
- Working a holiday or Sunday is allowed only when needed for required coverage. A tally of such days is kept for fairness; automatic comp-off scheduling is not built.
- A working employee counts toward every process they hold a primary assignment on.
- Public holidays are one shared calendar; per-brand holiday calendars are not modelled.
- Sample dates and holidays are fictional or approximate and fully editable.
- No authentication.

## 13. Left to the builder

UI styling and layout details, exact seed names and brands, solver weights and time limit, ORM and component library choices, how the before/after issue diff is displayed, test data fixtures beyond the demo scenario.
