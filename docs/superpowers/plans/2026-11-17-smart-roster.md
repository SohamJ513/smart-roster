# Smart Roster Management System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deployed web app where an ops manager generates, validates, edits and re-plans a monthly roster for 30+ employees across brands, processes and pods.

**Architecture:** Pure-Python domain core (`domain`, `calendar_rules`, `validator`, `solver`, `changes`) that knows nothing about the database or HTTP. A thin FastAPI layer loads a `Snapshot` from SQLAlchemy, calls the core, and serves JSON plus the built React app. The validator is independent of the solver and checks every roster, including manual edits.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, OR-Tools CP-SAT, pytest, httpx; React + Vite + TypeScript, TanStack Query, vitest; SQLite (`DATABASE_URL` allows PostgreSQL); Docker.

**Spec:** `docs/superpowers/specs/2026-11-17-smart-roster-design.md`

## Global Constraints

- Statuses: `WORK`, `WEEKLY_OFF`, `HOLIDAY`, `LEAVE`, `COMP_OFF`. Leave types: `planned`, `comp_off`. Roster status: `draft`, `published`.
- Operating rule presets: 365 days (weekdays 0-6, holidays_off false); daily except holidays (0-6, true); Sundays and holidays off (Mon-Sat = 0-5, true).
- Hard rules: coverage met on every operating day; no WORK on leave or comp-off; at most 6 consecutive working days; at least 4 non-working days in the month (both configurable via `Params`); one status per employee per day; locked entries respected; no double-counting across overlapping explicit shift windows ("General" = no window, never conflicts).
- Soft rules, in priority order: preferred weekly-off weekday; fair spread of Sunday and holiday work; fewer thin-coverage days.
- Required coverage always beats a preferred weekly off.
- The solver never returns "infeasible": coverage uses slack with a very large penalty and returns a shortfall list. Time limit about 10 seconds.
- Publishing with any ERROR requires explicit acknowledgement, which is recorded.
- No authentication, no notifications, no hosted AI. Conflict messages come from templates.
- One deployable service; `DATABASE_URL` selects SQLite (demo) or PostgreSQL; seed runs on first start when the database is empty; a "Reset demo data" action restores it.
- Sample data: 32-34 employees, 4 pods (lead is an employee), about 25 brands, 20 single-resource brands (80%), 5 brands with 2-3 employees, at least two processes needing 2 people, all three operating-rule presets, one or two brands with explicit Morning/Evening windows.

## Review Focus

1. A process with no assigned employees: every operating day gives a `NO_COVERAGE` error; nothing crashes.
2. An employee with no assignments: appears in the roster, counts toward no process, never causes an error.
3. Everyone assigned to a process on leave on the same day (infeasible): `generate` still returns within the time limit, with shortfalls listed.
4. February 2027 (28 days) and 31-day months: month boundaries are computed correctly; the rest-streak starts fresh at day 1 (documented assumption).
5. Leaves duplicated or dated outside the month, and a PATCH naming an unknown employee or a date outside the roster month: duplicates and outside dates are ignored by the core; PATCH returns 422.

---

## File Structure

```
roster-system/
  backend/
    app/
      domain.py          # dataclasses shared by the core (no DB, no HTTP)
      calendar_rules.py  # operating days and required staff
      validator.py       # validate(snapshot, entries) -> issues
      solver.py          # generate(...) with CP-SAT
      changes.py         # impact(...) and suggest(...)
      models.py, db.py   # SQLAlchemy tables and engine
      loader.py          # DB rows -> Snapshot
      seed.py            # demo dataset
      schemas.py         # Pydantic request/response models
      routers/config.py  # CRUD for config tables
      routers/rosters.py # generate/validate/patch/impact/suggest/publish/export
      main.py            # app, routers, static files
    tests/               # one test file per module above
    requirements.txt
  frontend/              # Vite + React + TS
  Dockerfile, README.md, .env.example, .gitignore
```

---

### Task 1: Scaffold, database models, domain types

**Files:** Create `backend/app/{domain,models,db}.py`, `backend/requirements.txt`, `backend/tests/test_models.py`, `.gitignore`. Run `git init`.

**Interfaces:**
- Produces (`domain.py`, frozen dataclasses): `ProcessCfg(id:int, brand_id:int, name:str, weekdays:frozenset[int], holidays_off:bool, min_staff:int, overrides_by_weekday:dict[int,int], overrides_by_date:dict[date,int], shift_start:time|None, shift_end:time|None)`; `EmployeeCfg(id:int, name:str, pod_id:int, weekly_off_mode:str, fixed_weekday:int|None, preferred_off_weekday:int|None)`; `AssignmentCfg(employee_id:int, process_id:int, role:str)`; `Params(max_consecutive:int=6, min_off_days:int=4)`; `Snapshot(year:int, month:int, employees:list[EmployeeCfg], processes:list[ProcessCfg], assignments:list[AssignmentCfg], holidays:frozenset[date], leaves:dict[int,frozenset[date]], params:Params)`; `Entry(employee_id:int, date:date, status:str, locked:bool=False, source:str="solver")`; `Issue(severity:str, code:str, message:str, date:date|None=None, process_id:int|None=None, employee_id:int|None=None)`.
- Produces (`models.py`): SQLAlchemy tables `Pod, Employee, Brand, Process, CoverageOverride, Assignment, Holiday, Leave, Roster, RosterEntry` with the fields in spec section 5; `db.py`: `engine`, `SessionLocal`, `init_db()` reading `DATABASE_URL` (default `sqlite:///./roster.db`).

- [ ] **Step 1:** `git init`; create `requirements.txt` (fastapi, uvicorn, sqlalchemy, ortools, pytest, httpx); install with `pip install --break-system-packages -r requirements.txt`.
- [ ] **Step 2: Test** in `test_models.py`: `test_create_brand_with_two_processes_and_assignments` (in-memory SQLite: one brand, two processes, one employee assigned to both; assert 2 assignment rows and that a second employee can be assigned to the same process); `test_leave_unique_per_employee_date` (inserting the same employee+date twice raises `IntegrityError`).
- [ ] **Step 3:** Run `cd backend && pytest tests/test_models.py -v`. Expected: FAIL (modules missing).
- [ ] **Step 4:** Implement `domain.py`, `models.py`, `db.py`. Add the unique constraint on Leave(employee_id, date) and foreign keys everywhere.
- [ ] **Step 5:** Run the same command. Expected: PASS.
- [ ] **Step 6:** Commit `feat: scaffold backend, models and domain types`.

### Task 2: Operating calendar rules

**Files:** Create `backend/app/calendar_rules.py`, `backend/tests/test_calendar_rules.py`.

**Interfaces:**
- Consumes: `ProcessCfg`.
- Produces: `is_operating(p:ProcessCfg, d:date, holidays:frozenset[date]) -> bool`; `required_staff(p:ProcessCfg, d:date, holidays:frozenset[date]) -> int` (0 when not operating; date override beats weekday override beats `min_staff`); `month_days(year:int, month:int) -> list[date]`.

- [ ] **Step 1: Tests:** `test_365_operates_on_sunday_and_holiday` (Sunday and a listed holiday both True); `test_daily_except_holidays_closed_on_holiday`; `test_sundays_and_holidays_off_closed_on_sunday` (weekdays 0-5); `test_date_override_beats_weekday_override` (min 1, Friday override 2, specific Friday date override 3 → 3); `test_required_staff_zero_when_closed`; `test_month_days_feb_2027_has_28`.
- [ ] **Step 2:** Run `pytest tests/test_calendar_rules.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the three functions.
- [ ] **Step 4:** Run again. Expected: PASS.
- [ ] **Step 5:** Commit `feat: operating calendar rules`.

### Task 3: Validator

**Files:** Create `backend/app/validator.py`, `backend/tests/test_validator.py`.

**Interfaces:**
- Consumes: `Snapshot`, `Entry`, `calendar_rules`.
- Produces: `validate(snap:Snapshot, entries:list[Entry]) -> list[Issue]`. Codes and severity: ERRORS `NO_COVERAGE` (required > 0 and no assigned employee is available that day), `UNDERSTAFFED` (some available but fewer than required), `WORK_ON_LEAVE`, `REST_RULE` (more than `max_consecutive` WORK days in a row), `MIN_OFF_DAYS`, `SHIFT_OVERLAP`; WARNINGS `PREF_OFF_VIOLATED`, `FIXED_OFF_VIOLATED`, `THIN_COVERAGE` (coverage exactly equals the minimum and the minimum is at least 2), `UNFAIR_HOLIDAY_WORK` (an employee's Sunday/holiday WORK days exceed the team average by 2 or more). "Available" = status WORK. Entries for unknown employees or dates outside the month are ignored. Each message names the date, process or employee, and what to do.

- [ ] **Step 1: Tests** (each builds a tiny Snapshot): `test_single_employee_on_leave_gives_no_coverage_error` (the brand's only employee off on an operating day → one `NO_COVERAGE`, severity ERROR, with that date and process id); `test_two_needed_one_working_is_understaffed`; `test_three_assigned_one_off_still_covered_no_error`; `test_work_on_leave_is_error`; `test_seven_work_days_in_a_row_is_rest_error` and `test_six_in_a_row_is_fine`; `test_overlapping_explicit_shifts_same_day_is_shift_overlap` and `test_general_processes_never_overlap`; `test_preferred_off_violated_is_warning_not_error`; `test_process_with_no_assignments_gives_no_coverage_every_operating_day`; `test_employee_with_no_assignments_causes_no_issue`; `test_entries_outside_month_or_unknown_employee_ignored`; `test_validator_does_not_mutate_inputs`.
- [ ] **Step 2:** Run `pytest tests/test_validator.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `validate`. Build per-day working sets once, then check each rule in a separate helper so each rule stays small.
- [ ] **Step 4:** Run again. Expected: PASS.
- [ ] **Step 5:** Commit `feat: roster validator with hard and soft rules`.

### Task 4: Solver

**Files:** Create `backend/app/solver.py`, `backend/tests/test_solver.py`.

**Interfaces:**
- Consumes: `Snapshot`, `Entry`, `validate`, `calendar_rules`.
- Produces: `generate(snap:Snapshot, locked:list[Entry]=[], window:tuple[date,date]|None=None, time_limit_s:float=10.0) -> SolveResult`, where `SolveResult(entries:list[Entry], issues:list[Issue])` and `issues = validate(snap, entries)`. One boolean per (employee, date); entry status derived afterwards: LEAVE/COMP_OFF from leaves, HOLIDAY for a non-working holiday, otherwise WEEKLY_OFF. When `window` is set, entries outside it are copied from `locked` and not changed. Objective: shortfall slack (very large weight) >> preference penalties >> fairness penalties.

- [ ] **Step 1: Tests:** `test_generated_roster_has_no_errors_for_feasible_input` (small team, all rules satisfiable → zero ERROR issues); `test_leave_is_never_scheduled_as_work`; `test_locked_entries_are_kept`; `test_only_employee_on_leave_returns_shortfall_not_exception` (single-resource brand, leave on a required day → returns within the time limit, issues contain `NO_COVERAGE` for that date); `test_everyone_on_leave_same_day_still_returns` (Review Focus 3); `test_preference_honoured_when_coverage_allows` and `test_coverage_beats_preference` (preferred off weekday would uncover a single-resource brand → employee works, no error, `PREF_OFF_VIOLATED` warning); `test_window_resolve_only_changes_inside_window`; `test_february_2027_28_days`.
- [ ] **Step 2:** Run `pytest tests/test_solver.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement with `ortools.sat.python.cp_model`. Coverage: for each (process, operating day) `sum(work[e,d] for assigned e) + slack >= required`; shift overlap: for employees assigned to two overlapping explicit-window processes, a cover variable per (employee, process, day) with `sum(cover over overlapping) <= 1` and `cover <= work`. Rest rule: for every window of `max_consecutive + 1` days, sum of work is at most `max_consecutive`. Fairness: minimise the max minus min of Sunday/holiday work counts.
- [ ] **Step 4:** Run again. Expected: PASS (each test under about 15 seconds).
- [ ] **Step 5:** Commit `feat: CP-SAT roster solver with slack-based shortfalls`.

### Task 5: Loader and seed data

**Files:** Create `backend/app/loader.py`, `backend/app/seed.py`, `backend/tests/test_seed.py`.

**Interfaces:**
- Consumes: `models`, `domain`, `generate`.
- Produces: `load_snapshot(session, year:int, month:int) -> Snapshot`; `seed_if_empty(session) -> bool`; `reset_demo(session) -> None`. Dataset follows Global Constraints "Sample data"; holidays seeded for Nov 2026 to Jan 2027 (builder verifies the real dates); a few planned leaves and one comp-off in the demo month; deterministic (no randomness).

- [ ] **Step 1: Tests:** `test_seed_has_at_least_30_employees_and_4_pods`; `test_about_80_percent_of_brands_are_single_resource` (between 0.75 and 0.85 of brands have exactly one assigned employee); `test_has_multi_employee_brand_with_shared_process_and_with_separate_processes`; `test_has_overlapping_shift_window_processes`; `test_seed_is_idempotent` (second call returns False, row counts unchanged); `test_demo_month_generates_with_no_errors` (generate for the demo month: zero ERROR issues).
- [ ] **Step 2:** Run `pytest tests/test_seed.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the loader (ignore duplicate or out-of-month leaves) and the seed.
- [ ] **Step 4:** Run again. Expected: PASS.
- [ ] **Step 5:** Commit `feat: snapshot loader and realistic demo dataset`.

### Task 6: Change impact and suggestions

**Files:** Create `backend/app/changes.py`, `backend/tests/test_changes.py`.

**Interfaces:**
- Consumes: `Snapshot`, `Entry`, `Issue`, `validate`, `generate`.
- Produces: `impact(snap, entries, new_leaves:dict[int,frozenset[date]]) -> ImpactResult(before:list[Issue], after:list[Issue], new_issues:list[Issue], resolved_issues:list[Issue], entries_after:list[Entry])` (leave days become `LEAVE` entries); `suggest(snap, entries, issue:Issue) -> list[Suggestion]`, `Suggestion(kind:str, description:str, entry_changes:list[Entry], resolves:bool)`. Kinds: `backup` (free employee, same pod first, then others, not on leave, within rest limit, no shift overlap; ranked by same-process assignment then lowest workload), `swap` (move an assigned employee's weekly off to a day where coverage holds), `resolve` (partial `generate` over a window of about 7 days around the issue date, others locked).

- [ ] **Step 1: Tests:** `test_leave_of_single_resource_employee_creates_no_coverage_issue`; `test_one_of_three_on_leave_creates_no_issue_when_minimum_still_met`; `test_impact_lists_new_issue_and_leaves_before_unchanged`; `test_backup_suggestion_prefers_same_pod`; `test_backup_never_suggests_someone_on_leave_or_over_rest_limit`; `test_applying_a_resolving_suggestion_removes_the_issue` (apply `entry_changes`, re-validate, the issue is gone).
- [ ] **Step 2:** Run `pytest tests/test_changes.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement both functions; `impact` and `suggest` must not mutate their inputs.
- [ ] **Step 4:** Run again. Expected: PASS.
- [ ] **Step 5:** Commit `feat: change impact analysis and fix suggestions`.

### Task 7: Config CRUD API

**Files:** Create `backend/app/schemas.py`, `backend/app/routers/config.py`, `backend/app/main.py`, `backend/tests/test_config_api.py`.

**Interfaces:**
- Produces: REST `GET/POST/PUT/DELETE` at `/api/{pods,employees,brands,processes,assignments,holidays,leaves,overrides}`; `GET /api/health` returns `{"status":"ok"}`; `POST /api/demo/reset`. `main.py` runs `init_db()` and `seed_if_empty` on startup.

- [ ] **Step 1: Tests** (FastAPI `TestClient`, temp DB): `test_create_brand_process_employee_assignment_roundtrip`; `test_delete_assignment_then_validate_shows_no_coverage` is deferred to Task 8; here `test_invalid_weekday_value_returns_422`; `test_duplicate_leave_returns_409`; `test_health_ok`; `test_reset_demo_restores_seed_counts`.
- [ ] **Step 2:** Run `pytest tests/test_config_api.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement schemas, routers and app wiring.
- [ ] **Step 4:** Run again. Expected: PASS.
- [ ] **Step 5:** Commit `feat: configuration API`.

### Task 8: Roster API

**Files:** Create `backend/app/routers/rosters.py`, `backend/tests/test_rosters_api.py`; modify `backend/app/main.py`.

**Interfaces:**
- Produces: `POST /api/rosters/generate {year,month}` → `{roster_id, issues}`; `GET /api/rosters/{id}` → entries; `GET /api/rosters/{id}/validate` → issues; `PATCH /api/rosters/{id}/entries {employee_id,date,status}` → `{issues, new_issues, resolved_issues}` (entry saved as `manual`, `locked=true`); `POST /api/rosters/{id}/impact {leaves:[{employee_id,date,type}]}` (what-if, nothing saved); `POST /api/rosters/{id}/apply-leave` (saves the leave and entries); `GET /api/rosters/{id}/suggestions?date=&process_id=&code=`; `POST /api/rosters/{id}/apply-suggestion`; `POST /api/rosters/{id}/publish {acknowledged_issue_codes:[...]}` (409 if ERRORs exist and not acknowledged; acknowledgement stored); `GET /api/rosters/{id}/export.csv`.

- [ ] **Step 1: Tests:** `test_generate_for_demo_month_has_entries_for_every_employee_every_day`; `test_patch_to_leave_a_single_resource_employee_returns_new_no_coverage_issue`; `test_patch_unknown_employee_or_date_outside_month_returns_422`; `test_publish_blocked_with_errors_then_allowed_with_acknowledgement`; `test_impact_does_not_change_stored_roster`; `test_export_csv_has_header_and_one_row_per_employee`; `test_end_to_end_demo_scenario` (generate, apply a leave for a single-resource employee, request suggestions, apply the first resolving one, issue gone).
- [ ] **Step 2:** Run `pytest tests/test_rosters_api.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the router using `load_snapshot`, `generate`, `validate`, `impact`, `suggest`.
- [ ] **Step 4:** Run again, then the whole backend suite `pytest -q`. Expected: all PASS.
- [ ] **Step 5:** Commit `feat: roster API with validation, changes and publish gate`.

### Task 9: Frontend scaffold and configuration screens

**Files:** Create `frontend/` (Vite React TS), `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/pages/Config*.tsx`, `frontend/src/App.tsx`, `frontend/src/api.test.ts`.

**Interfaces:**
- Produces: typed client functions in `api.ts` mirroring every endpoint from Tasks 7-8 (for example `generateRoster(year:number, month:number): Promise<{roster_id:number; issues:Issue[]}>`); `types.ts` mirrors `Issue`, `Entry`, `Status`; routes `/config/pods`, `/config/employees`, `/config/brands`, `/config/processes`, `/config/assignments`, `/config/holidays`, `/config/leaves`. Vite dev server proxies `/api` to the backend.

- [ ] **Step 1: Test** (vitest) in `api.test.ts`: `buildQuery({date:"2026-12-05", process_id:3})` returns `"date=2026-12-05&process_id=3"`.
- [ ] **Step 2:** Run `cd frontend && npm test`. Expected: FAIL.
- [ ] **Step 3:** Scaffold with `npm create vite@latest`, add TanStack Query and react-router; implement `api.ts` and the config pages (table plus add/edit/delete form each; the process form includes the operating-rule presets, shift window, and coverage overrides).
- [ ] **Step 4:** Run `npm test` (expected PASS) and `npm run build` (expected success).
- [ ] **Step 5:** Commit `feat: frontend scaffold and configuration screens`.

### Task 10: Roster views, issues panel and editing

**Files:** Create `frontend/src/pages/Roster*.tsx`, `frontend/src/components/{RosterGrid,CoverageStrip,IssuesPanel,StatusChip}.tsx`, `frontend/src/lib/coverage.ts`, `frontend/src/lib/coverage.test.ts`.

**Interfaces:**
- Consumes: Task 8 client functions.
- Produces: `coverageCell(required:number, working:number): "ok"|"thin"|"gap"|"closed"` in `coverage.ts`; views at `/roster/company`, `/roster/pod/:id`, `/roster/brand/:id`, `/roster/process/:id`, `/roster/employee/:id`; month picker and Generate button; clicking a cell opens a status menu that calls PATCH and shows the new and resolved issues; issues panel with severity filter and click-to-jump.

- [ ] **Step 1: Test:** `coverageCell(0,0)` is `"closed"`; `(2,1)` is `"gap"`; `(2,2)` is `"thin"`; `(2,3)` is `"ok"`; `(1,1)` is `"ok"` (single-resource processes are not thin).
- [ ] **Step 2:** Run `npm test`. Expected: FAIL.
- [ ] **Step 3:** Implement the lib function, the shared grid and the five views (same data, different filters). Colour and also label every status so meaning never depends on colour alone.
- [ ] **Step 4:** Run `npm test` and `npm run build`; then start backend and frontend and check in a browser that generating the demo month shows all five views without console errors.
- [ ] **Step 5:** Commit `feat: roster views, issues panel and inline editing`.

### Task 11: Change flow and publish UI

**Files:** Create `frontend/src/components/{ChangePanel,SuggestionList,PublishDialog}.tsx`; modify the roster pages.

**Interfaces:**
- Consumes: `impact`, `apply-leave`, `suggestions`, `apply-suggestion`, `publish` client functions.

- [ ] **Step 1:** Implement the "Add leave" what-if panel: choose employee and dates, show before/after issues, then Apply. For each gap, show ranked suggestions (backup, swap, partial re-solve) with a one-line impact; applying one re-validates and refreshes. Publish dialog lists ERRORs and requires ticking acknowledgement.
- [ ] **Step 2:** Run `npm run build`. Expected: success.
- [ ] **Step 3:** In a browser, walk the demo scenario: generate, add leave for a single-resource employee, see the gap, apply a suggestion, publish. Confirm nothing in the console.
- [ ] **Step 4:** Commit `feat: change flow with suggestions and publish gate`.

### Task 12: Deployment and README

**Files:** Create `Dockerfile`, `.env.example`, `README.md`; modify `backend/app/main.py` (serve `frontend/dist` when present).

- [ ] **Step 1:** Multi-stage Dockerfile: node build of the frontend, then Python image running `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. `.env.example` lists `DATABASE_URL` and `PORT`.
- [ ] **Step 2:** Run `docker build -t roster .` then `docker run -p 8000:8000 roster`; open `http://localhost:8000` and confirm the app loads with seeded data and `/api/health` returns ok. (If Docker is unavailable here, build the frontend and run `uvicorn` locally, and say so.)
- [ ] **Step 3:** README sections: what it is, setup and run, tests, assumptions (spec section 12), a how-to for the demo scenario, and the eight "How do you think" answers written from the actual implementation.
- [ ] **Step 4:** Deploy to Render, Railway or Fly (needs the author's account); record the public URL. Run the demo scenario on the live URL.
- [ ] **Step 5:** Commit `docs: deployment files and README`.

---

## Self-Review Notes

- Every spec section maps to a task: data model (1), calendar rules (2), validator and hard/soft rules (3), solver (4), sample data (5), change handling (6, 8, 11), config and views (7, 9, 10), publish rule (8, 11), deployment (12).
- Signatures used later (`generate`, `validate`, `impact`, `suggest`, `Snapshot`, `Entry`, `Issue`) are defined once in Tasks 1, 3, 4 and 6.
- Extras from spec section 9 (comparison of alternative rosters, approval status) are intentionally not planned; add only if time remains.
