def test_responses_carry_a_server_timing_header(client):
    r = client.get("/api/health")
    assert r.headers["Server-Timing"].startswith("app;dur=")


def test_slow_requests_are_logged(client, caplog, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "SLOW_REQUEST_MS", 0)      # treat every request as slow
    with caplog.at_level("WARNING"):
        client.get("/api/health")
    assert any("SLOW GET /api/health" in r.message for r in caplog.records)