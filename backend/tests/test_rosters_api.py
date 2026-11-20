import csv
import io

HOLIDAY_FRI = "2026-12-25"   # public holiday; processes that work holidays still need cover


def owner_of(client, brand_name, process_name="CS"):
    brand = next(b for b in client.get("/api/brands").json() if b["name"] == brand_name)
    proc = next(p for p in client.get("/api/processes").json()
                if p["brand_id"] == brand["id"] and p["name"] == process_name)
    asg = next(a for a in client.get("/api/assignments").json() if a["process_id"] == proc["id"])
    return asg["employee_id"], proc["id"]


def generate(client, year=2026, month=12):
    r = client.post("/api/rosters/generate", json={"year": year, "month": month})
    assert r.status_code == 200, r.text
    return r.json()


def errors(issues):
    return [i for i in issues if i["severity"] == "ERROR"]


def test_generate_for_demo_month_has_entries_for_every_employee_every_day(client):
    out = generate(client)
    roster = client.get(f"/api/rosters/{out['roster_id']}").json()
    n_emp = len(client.get("/api/employees").json())
    assert len(roster["entries"]) == n_emp * 31 and roster["status"] == "draft"
    assert errors(out["issues"]) == []


def test_patch_to_leave_a_single_resource_employee_returns_new_no_coverage_issue(client):
    rid = generate(client)["roster_id"]
    emp, proc = owner_of(client, "Bloom & Co")
    r = client.patch(f"/api/rosters/{rid}/entries", json={"employee_id": emp, "date": "2026-12-09", "status": "LEAVE"})
    assert r.status_code == 200
    new = [(i["code"], i["date"], i["process_id"]) for i in r.json()["new_issues"]]
    assert ("NO_COVERAGE", "2026-12-09", proc) in new


def test_patch_unknown_employee_or_date_outside_month_returns_422(client):
    rid = generate(client)["roster_id"]
    emp, _ = owner_of(client, "Bloom & Co")
    url = f"/api/rosters/{rid}/entries"
    assert client.patch(url, json={"employee_id": 99999, "date": "2026-12-09", "status": "WORK"}).status_code == 422
    assert client.patch(url, json={"employee_id": emp, "date": "2027-01-05", "status": "WORK"}).status_code == 422
    assert client.patch(url, json={"employee_id": emp, "date": "2026-12-09", "status": "NAP"}).status_code == 422


def test_publish_clean_roster_ok(client):
    rid = generate(client)["roster_id"]
    r = client.post(f"/api/rosters/{rid}/publish", json={})
    assert r.status_code == 200 and client.get(f"/api/rosters/{rid}").json()["status"] == "published"


def test_publish_blocked_with_errors_then_allowed_with_acknowledgement(client):
    rid = generate(client)["roster_id"]
    emp, _ = owner_of(client, "Bloom & Co")
    client.patch(f"/api/rosters/{rid}/entries", json={"employee_id": emp, "date": "2026-12-09", "status": "LEAVE"})
    blocked = client.post(f"/api/rosters/{rid}/publish", json={})
    assert blocked.status_code == 409 and errors(blocked.json()["detail"]["issues"])
    ok = client.post(f"/api/rosters/{rid}/publish", json={"acknowledged_issue_codes": ["NO_COVERAGE"]})
    assert ok.status_code == 200
    roster = client.get(f"/api/rosters/{rid}").json()
    assert roster["status"] == "published" and roster["acknowledged_codes"] == ["NO_COVERAGE"]


def test_impact_does_not_change_stored_roster(client):
    rid = generate(client)["roster_id"]
    emp, proc = owner_of(client, "PureRoots")
    before = client.get(f"/api/rosters/{rid}").json()["entries"]
    n_leaves = len(client.get("/api/leaves").json())
    r = client.post(f"/api/rosters/{rid}/impact", json={"leaves": [{"employee_id": emp, "date": HOLIDAY_FRI}]})
    assert r.status_code == 200
    assert any(i["code"] == "NO_COVERAGE" and i["process_id"] == proc for i in r.json()["new_issues"])
    assert client.get(f"/api/rosters/{rid}").json()["entries"] == before
    assert len(client.get("/api/leaves").json()) == n_leaves


def test_export_csv_has_header_and_one_row_per_employee(client):
    rid = generate(client)["roster_id"]
    r = client.get(f"/api/rosters/{rid}/export.csv")
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    rows = list(csv.reader(io.StringIO(r.text)))
    assert len(rows) == 1 + len(client.get("/api/employees").json())
    assert len(rows[0]) == 2 + 31


def test_end_to_end_demo_scenario(client):
    rid = generate(client)["roster_id"]
    emp, proc = owner_of(client, "PureRoots")                       # single-resource brand open on holidays
    r = client.post(f"/api/rosters/{rid}/apply-leave", json={"leaves": [{"employee_id": emp, "date": HOLIDAY_FRI}]})
    assert r.status_code == 200
    gap = next(i for i in r.json()["issues"] if i["code"] == "NO_COVERAGE" and i["process_id"] == proc)
    sugg = client.get(f"/api/rosters/{rid}/suggestions",
                      params={"date": gap["date"], "process_id": proc, "code": "NO_COVERAGE"}).json()
    best = next(s for s in sugg if s["resolves"])
    done = client.post(f"/api/rosters/{rid}/apply-suggestion", json={"entry_changes": best["entry_changes"]})
    assert done.status_code == 200
    assert not any(i["code"] == "NO_COVERAGE" and i["process_id"] == proc for i in
                   client.get(f"/api/rosters/{rid}/validate").json())


def test_coverage_endpoint_reports_required_and_working(client):
    rid = generate(client)["roster_id"]
    emp, proc = owner_of(client, "PureRoots")
    bloom_emp, bloom_proc = owner_of(client, "Bloom & Co")

    def find(pid, d):
        return next(c for c in client.get(f"/api/rosters/{rid}/coverage").json() if c["process_id"] == pid and c["date"] == d)

    assert (find(proc, HOLIDAY_FRI)["required"], find(proc, HOLIDAY_FRI)["working"]) == (1, 1)
    assert find(bloom_proc, HOLIDAY_FRI)["required"] == 0                      # closed on the public holiday
    client.patch(f"/api/rosters/{rid}/entries", json={"employee_id": emp, "date": HOLIDAY_FRI, "status": "LEAVE"})
    assert find(proc, HOLIDAY_FRI)["working"] == 0


def test_editing_a_published_roster_returns_it_to_draft(client):
    rid = generate(client)["roster_id"]
    assert client.post(f"/api/rosters/{rid}/publish", json={"acknowledged_issue_codes": []}).status_code == 200
    emp = client.get("/api/employees").json()[0]["id"]
    client.patch(f"/api/rosters/{rid}/entries", json={"employee_id": emp, "date": "2026-12-09", "status": "LEAVE"})
    got = client.get(f"/api/rosters/{rid}").json()
    assert got["status"] == "draft"


def test_csv_export_neutralises_formula_names(client):
    rid = generate(client)["roster_id"]
    emp = client.get("/api/employees").json()[0]
    client.put(f"/api/employees/{emp['id']}", json={**emp, "name": "=HYPERLINK(\"http://x\")"})
    rows = list(csv.reader(io.StringIO(client.get(f"/api/rosters/{rid}/export.csv").text)))
    assert all(not r[0].startswith("=") for r in rows[1:])
    assert any(r[0].startswith("'=") for r in rows[1:])
