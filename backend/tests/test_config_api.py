

def test_health_ok(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_create_brand_process_employee_assignment_roundtrip(client):
    pod = client.post("/api/pods", json={"name": "Epsilon"}).json()
    emp = client.post("/api/employees", json={"name": "Tara", "pod_id": pod["id"]}).json()
    brand = client.post("/api/brands", json={"name": "Fresh Co"}).json()
    proc = client.post("/api/processes", json={"brand_id": brand["id"], "name": "CS", "weekdays": [0, 1, 2, 3, 4, 5],
                                              "holidays_off": True, "min_staff": 2}).json()
    asg = client.post("/api/assignments", json={"employee_id": emp["id"], "process_id": proc["id"]})
    assert asg.status_code == 201 and asg.json()["role"] == "primary"
    assert proc["min_staff"] == 2 and proc["weekdays"] == [0, 1, 2, 3, 4, 5]
    assert any(a["id"] == asg.json()["id"] for a in client.get("/api/assignments").json())
    assert client.put(f"/api/employees/{emp['id']}", json={"name": "Tara S", "pod_id": pod["id"]}).json()["name"] == "Tara S"


def test_invalid_weekday_value_returns_422(client):
    brand = client.get("/api/brands").json()[0]
    r = client.post("/api/processes", json={"brand_id": brand["id"], "name": "X", "weekdays": [0, 9],
                                            "holidays_off": False, "min_staff": 1})
    assert r.status_code == 422


def test_fixed_weekly_off_requires_a_weekday(client):
    pod = client.get("/api/pods").json()[0]
    r = client.post("/api/employees", json={"name": "Z", "pod_id": pod["id"], "weekly_off_mode": "fixed"})
    assert r.status_code == 422


def test_duplicate_leave_returns_409(client):
    emp = client.get("/api/employees").json()[0]
    body = {"employee_id": emp["id"], "date": "2026-12-30", "type": "planned"}
    assert client.post("/api/leaves", json=body).status_code == 201
    assert client.post("/api/leaves", json=body).status_code == 409


def test_unknown_reference_returns_409(client):
    r = client.post("/api/assignments", json={"employee_id": 99999, "process_id": 99999})
    assert r.status_code == 409


def test_delete_process_removes_its_assignments(client):
    proc_id = client.get("/api/processes").json()[0]["id"]
    before = len(client.get("/api/assignments").json())
    n = sum(1 for a in client.get("/api/assignments").json() if a["process_id"] == proc_id)
    assert n >= 1
    assert client.delete(f"/api/processes/{proc_id}").status_code == 204
    assert len(client.get("/api/assignments").json()) == before - n


def test_reset_demo_restores_seed_counts(client):
    n_brands, n_asg = len(client.get("/api/brands").json()), len(client.get("/api/assignments").json())
    brand_id = client.get("/api/brands").json()[0]["id"]
    assert client.delete(f"/api/brands/{brand_id}").status_code == 204
    assert len(client.get("/api/brands").json()) == n_brands - 1
    assert client.post("/api/demo/reset").status_code == 200
    assert (len(client.get("/api/brands").json()), len(client.get("/api/assignments").json())) == (n_brands, n_asg)
